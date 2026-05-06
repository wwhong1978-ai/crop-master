"""
缩略图缓存管理器
- 缩略图缩小到 200px
- 懒加载：只加载可见区域 + 预加载
- 动态卸载不可见的缩略图
"""

from PyQt5.QtCore import QObject, pyqtSignal, QThread, QSize
from PyQt5.QtGui import QPixmap, QImage
from pathlib import Path
from collections import OrderedDict
import weakref


class ThumbnailCache(QObject):
    """
    缩略图缓存管理器
    
    策略：
    1. 缩略图统一缩小到 200px 宽度
    2. 只缓存可见区域 + 上下各预加载 5 张
    3. 超出范围的缩略图从缓存中移除
    4. 使用 LRU 淘汰机制
    """
    
    # 信号
    thumbnail_ready = pyqtSignal(int, QPixmap)  # (索引，缩略图)
    cache_updated = pyqtSignal()  # 缓存更新信号
    
    # 配置
    THUMB_WIDTH = 180  # 缩略图宽度（留边距后）
    MAX_CACHE_SIZE = 50  # 最大缓存数量
    PRELOAD_COUNT = 5  # 预加载数量（可见区域上下各 N 张）
    
    def __init__(self):
        super().__init__()
        # 缓存：{index: QPixmap}
        self._cache = OrderedDict()
        # 所有图片路径
        self._image_paths = []
        # 可见区域
        self._visible_start = 0
        self._visible_end = 0
    
    def set_images(self, image_paths: list):
        """设置图片列表（清空缓存）"""
        self._image_paths = image_paths
        self._cache.clear()
        self._visible_start = 0
        self._visible_end = 0
    
    def get_thumbnail(self, index: int) -> QPixmap:
        """
        获取缩略图（如果未加载则返回 None）
        """
        if index < 0 or index >= len(self._image_paths):
            return None
        
        if index in self._cache:
            # LRU：访问过的移到末尾
            self._cache.move_to_end(index)
            return self._cache[index]
        
        return None
    
    def update_visible_range(self, start: int, end: int):
        """
        更新可见区域，触发懒加载
        """
        self._visible_start = max(0, start)
        self._visible_end = min(len(self._image_paths) - 1, end)
        
        # 计算需要加载的范围（可见区域 + 预加载）
        load_start = max(0, self._visible_start - self.PRELOAD_COUNT)
        load_end = min(len(self._image_paths) - 1, self._visible_end + self.PRELOAD_COUNT)
        
        # 加载需要的缩略图
        for i in range(load_start, load_end + 1):
            if i not in self._cache:
                self._load_thumbnail_async(i)
        
        # 清理超出范围的缓存（保留 LRU）
        self._cleanup_cache(load_start, load_end)
    
    def _load_thumbnail_async(self, index: int):
        """异步加载缩略图"""
        if index < 0 or index >= len(self._image_paths):
            return
        
        path = self._image_paths[index]
        
        # 在工作线程中加载
        worker = ThumbnailLoaderWorker(path, index, self.THUMB_WIDTH)
        worker.finished.connect(self._on_thumbnail_loaded)
        worker.start()
    
    def _on_thumbnail_loaded(self, index: int, pixmap: QPixmap):
        """缩略图加载完成"""
        if pixmap.isNull():
            return
        
        # 添加到缓存
        if index in self._cache:
            del self._cache[index]
        self._cache[index] = pixmap
        
        # LRU 淘汰：如果超出最大缓存数，移除最旧的
        while len(self._cache) > self.MAX_CACHE_SIZE:
            self._cache.popitem(last=False)
        
        # 发送信号
        self.thumbnail_ready.emit(index, pixmap)
        self.cache_updated.emit()
    
    def _cleanup_cache(self, keep_start: int, keep_end: int):
        """清理缓存，只保留需要范围内的"""
        # 找出需要移除的索引
        to_remove = []
        for idx in self._cache.keys():
            if idx < keep_start or idx > keep_end:
                to_remove.append(idx)
        
        # 移除（保留 LRU 顺序）
        for idx in to_remove:
            if idx in self._cache:
                del self._cache[idx]
    
    def clear(self):
        """清空缓存"""
        self._cache.clear()
        self._image_paths = []
        self._visible_start = 0
        self._visible_end = 0


class ThumbnailLoaderWorker(QThread):
    """单张缩略图加载线程"""
    
    finished = pyqtSignal(int, QPixmap)
    
    def __init__(self, image_path: Path, index: int, thumb_width: int):
        super().__init__()
        self.image_path = image_path
        self.index = index
        self.thumb_width = thumb_width
    
    def run(self):
        try:
            from PIL import Image
            
            # 加载并缩小
            img = Image.open(self.image_path)
            
            # 计算高度（保持比例）
            scale = self.thumb_width / img.width
            thumb_height = max(1, int(img.height * scale))
            
            # 缩小缩略图
            img.thumbnail((self.thumb_width, self.thumb_width * 2), Image.Resampling.LANCZOS)
            
            # 转 RGB
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # 转 QPixmap
            data = img.tobytes('raw', 'RGB')
            qimg = QImage(data, img.width, img.height, img.width * 3, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg)
            
            self.finished.emit(self.index, pixmap)
            
        except Exception as e:
            print(f"加载缩略图失败 {self.image_path}: {e}")
            self.finished.emit(self.index, QPixmap())
