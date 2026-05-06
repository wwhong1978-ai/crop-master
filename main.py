# 主窗口 - 图片裁剪工具 V5.0
import sys
import os
from pathlib import Path
from PIL import Image
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                            QLabel, QScrollArea, QScrollBar, QSpinBox, QLineEdit,
                            QGroupBox, QMessageBox, QProgressBar, QListWidget,
                            QListWidgetItem, QAbstractItemView, QSplitter, QFileDialog)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize, QRect, QPoint, QTimer
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QIcon

from thumbnail_cache import ThumbnailCache

class ThumbnailLoaderThread(QThread):
    """缩略图加载线程（兼容旧版，逐步迁移到新缓存系统）"""
    finished = pyqtSignal(list)  # [(path, thumbnail_data), ...]
    progress = pyqtSignal(int, int)
    error = pyqtSignal(str)
    
    def __init__(self, folder_path):
        super().__init__()
        self.folder_path = folder_path
    
    def run(self):
        try:
            from image_processor import ImageProcessor
            processor = ImageProcessor()
            paths = processor.scan_images(self.folder_path)
            
            results = []
            for i, path in enumerate(paths):
                try:
                    # 加载并缩小到缩略图尺寸
                    img = processor.load_image(path)
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    
                    # 缩小到 200px 宽度
                    thumb_width = 180
                    scale = thumb_width / img.width
                    thumb_height = max(1, int(img.height * scale))
                    img.thumbnail((thumb_width, thumb_width * 2), Image.Resampling.LANCZOS)
                    
                    data = img.tobytes('raw', 'RGB')
                    qimg = QImage(data, img.width, img.height, img.width * 3, QImage.Format_RGB888)
                    pixmap = QPixmap.fromImage(qimg)
                    results.append((path, pixmap))
                except Exception as e:
                    print(f"加载缩略图失败 {path}: {e}")
                
                self.progress.emit(i + 1, len(paths))
            
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        
        from config import ConfigManager
        self.config_manager = ConfigManager()
        self.config = self.config_manager.load_config()
        
        # 缩略图缓存管理器（懒加载）
        self.thumbnail_cache = ThumbnailCache()
        
        # 数据
        self.image_paths = []  # 所有图片路径
        self.thumbnails = {}  # 缩略图缓存 {path: QPixmap}（兼容旧代码）
        self.processed_indices = set()  # 已处理图片索引
        
        # 裁剪选区
        self.crop_rect = None  # (left, top, width, height)
        self.is_dragging = False
        self.drag_start = None
        
        # 尺寸比例跟踪
        self.ratio_applied = False  # 是否已应用尺寸比例
        self.applied_ratio = None  # 已应用的比例
        
        self.init_ui()
        self.load_saved_config()
    
    def init_ui(self):
        self.setWindowTitle("图片裁剪工具 V6.1")
        self.setGeometry(100, 100, 1400, 900)
        
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # 左侧缩略图侧边栏
        sidebar_group = self.create_sidebar()
        main_layout.addWidget(sidebar_group, 0)
        
        # 右侧工作区（图片显示 + 底部控制）
        right_layout = QVBoxLayout()
        right_layout.setSpacing(5)
        
        # 中间工作区
        work_group = self.create_work_area()
        right_layout.addWidget(work_group, 1)
        
        # 底部控制栏
        bottom_group = self.create_bottom_bar()
        right_layout.addWidget(bottom_group, 0)
        
        main_layout.addLayout(right_layout, 1)
        
        self.setLayout(main_layout)
        self.apply_styles()
    
    def create_sidebar(self):
        """左侧缩略图侧边栏"""
        group = QGroupBox("")
        group.setFixedWidth(200)
        layout = QVBoxLayout()
        layout.setSpacing(3)
        layout.setContentsMargins(3, 3, 3, 3)
        
        # 顶部按钮行
        self.btn_open_folder = QPushButton("打开文件夹")
        self.btn_open_folder.clicked.connect(self.open_folder)
        layout.addWidget(self.btn_open_folder)
        
        # 缩略图列表
        self.thumbnail_list = QListWidget()
        self.thumbnail_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.thumbnail_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.thumbnail_list.itemClicked.connect(self.on_thumbnail_clicked)
        self.thumbnail_list.setStyleSheet("QListWidget::item { border: none; }")
        
        # 监听滚动事件实现懒加载
        scrollbar = self.thumbnail_list.verticalScrollBar()
        scrollbar.valueChanged.connect(self.on_scroll_changed)
        
        layout.addWidget(self.thumbnail_list, 1)
        
        group.setLayout(layout)
        return group
    
    def create_work_area(self):
        """中间工作区"""
        group = QGroupBox("")
        layout = QVBoxLayout()
        
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(600, 500)  # 更大
        self.image_label.setStyleSheet("border: 1px solid #ccc; background-color: #f0f0f0;")
        self.image_label.setContextMenuPolicy(Qt.CustomContextMenu)
        self.image_label.customContextMenuRequested.connect(self.show_context_menu)
        
        # 安装事件处理拖拽和缩放 - 使用正确的方法名
        self.image_label.mousePressEvent = self.handle_mouse_press
        self.image_label.mouseMoveEvent = self.handle_mouse_move
        self.image_label.mouseReleaseEvent = self.handle_mouse_release
        self.image_label.wheelEvent = self.wheel_event
        self.image_label.setMouseTracking(True)  # 启用鼠标追踪
        
        layout.addWidget(self.image_label)
        
        # 图片信息移到下面，这里不显示了
        
        group.setLayout(layout)
        return group
    
    def create_bottom_bar(self):
        """底部控制栏 - V6.0 最终布局"""
        group = QGroupBox("")
        layout = QVBoxLayout()
        
        # 第一行：进度条（高度 10px）
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(True)  # 始终显示
        self.progress_bar.setFixedHeight(10)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # 第二行：裁剪尺寸 + 选框百分比
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("裁剪宽度："))
        self.spin_width = QSpinBox()
        self.spin_width.setRange(1, 9999)
        self.spin_width.setValue(1200)
        self.spin_width.setSuffix(" px")
        self.spin_width.valueChanged.connect(self.on_size_changed)
        size_layout.addWidget(self.spin_width)
        
        size_layout.addWidget(QLabel("  裁剪高度："))
        self.spin_height = QSpinBox()
        self.spin_height.setRange(1, 9999)
        self.spin_height.setValue(1200)
        self.spin_height.setSuffix(" px")
        self.spin_height.valueChanged.connect(self.on_size_changed)
        size_layout.addWidget(self.spin_height)
        
        # 添加选框大小百分比设置
        size_layout.addWidget(QLabel("  选框大小："))
        self.spin_crop_ratio = QSpinBox()
        self.spin_crop_ratio.setRange(10, 100)
        self.spin_crop_ratio.setValue(90)
        self.spin_crop_ratio.setSuffix(" %")
        self.spin_crop_ratio.setFixedWidth(80)
        self.spin_crop_ratio.valueChanged.connect(self.on_crop_ratio_changed)
        size_layout.addWidget(self.spin_crop_ratio)
        
        # 添加应用尺寸按钮
        self.btn_apply_size = QPushButton("应用尺寸到选框")
        self.btn_apply_size.clicked.connect(self.apply_size_to_crop)
        size_layout.addWidget(self.btn_apply_size)
        
        # 添加居中按钮
        self.btn_center = QPushButton("居中")
        self.btn_center.clicked.connect(self.center_crop_rect)
        size_layout.addWidget(self.btn_center)
        
        size_layout.addStretch()
        layout.addLayout(size_layout)
        
        # 第三行：输出目录 + 裁剪按钮
        output_layout = QHBoxLayout()
        
        # 左边：选择输出目录按钮（加大）
        self.btn_select_output = QPushButton("选择输出目录")
        self.btn_select_output.clicked.connect(self.select_output_dir)
        self.btn_select_output.setFixedSize(150, 40)  # 加大按钮
        output_layout.addWidget(self.btn_select_output)
        
        # 中间：输出目录标签
        self.lbl_output_dir = QLabel("未选择输出目录")
        output_layout.addWidget(self.lbl_output_dir, 1)
        
        # 右边：裁剪按钮（居右）
        self.btn_crop_single = QPushButton("单图裁剪")
        self.btn_crop_single.clicked.connect(self.crop_single)
        self.btn_crop_single.setEnabled(False)
        self.btn_crop_single.setFixedSize(120, 40)
        output_layout.addWidget(self.btn_crop_single)
        
        self.btn_crop_batch = QPushButton("批量裁剪")
        self.btn_crop_batch.clicked.connect(self.crop_batch)
        self.btn_crop_batch.setEnabled(False)
        self.btn_crop_batch.setFixedSize(120, 40)
        output_layout.addWidget(self.btn_crop_batch)
        
        layout.addLayout(output_layout)
        
        # 第四行：状态信息（所有居中，黑色，字号 +2）
        self.lbl_status = QLabel("已处理：0/0  图片：0x0 | 未加载图片")
        self.lbl_status.setStyleSheet("color: #000000; font-size: 15px; font-weight: bold;")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_status)
        
        group.setLayout(layout)
        return group
    
    def apply_styles(self):
        """样式"""
        self.setStyleSheet("""
            QWidget { font-family: "Segoe UI", Microsoft YaHei; font-size: 13px; }
            QGroupBox { border: 1px solid #E0E0E0; border-radius: 5px; margin-top: 5px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; }
            QPushButton { background-color: #F0F0F0; border: 1px solid #CCC; border-radius: 4px; padding: 5px 15px; }
            QPushButton:hover { background-color: #E5E5E5; }
            QPushButton:disabled { color: #999; }
            QSpinBox, QLineEdit { border: 1px solid #CCC; border-radius: 3px; padding: 3px; }
            QListWidget { border: 1px solid #ccc; }
            QListWidget::item:selected { background-color: #0078D4; }
        """)
    
    def load_saved_config(self):
        """加载保存的配置"""
        self.spin_width.setValue(self.config.get('crop_width', 800))
        self.spin_height.setValue(self.config.get('crop_height', 600))
        self.spin_crop_ratio.setValue(self.config.get('crop_ratio', 90))
        
        output_dir = self.config.get('output_dir', '')
        if output_dir:
            self.lbl_output_dir.setText(output_dir)
        
        last_folder = self.config.get('last_folder', '')
        if last_folder and os.path.exists(last_folder):
            self.load_folder(last_folder)
    
    def save_current_config(self):
        """保存当前配置"""
        self.config['crop_width'] = self.spin_width.value()
        self.config['crop_height'] = self.spin_height.value()
        self.config['crop_ratio'] = self.spin_crop_ratio.value()
        self.config['output_dir'] = self.lbl_output_dir.text()
        if hasattr(self, 'current_folder'):
            self.config['last_folder'] = self.current_folder
        
        self.config_manager.save_config(self.config)
    
    def open_folder(self):
        """打开文件夹"""
        folder = QFileDialog.getExistingDirectory(self, "选择图片文件夹")
        if folder:
            self.load_folder(folder)
    
    def load_folder(self, folder):
        """加载文件夹"""
        self.current_folder = folder
        self.save_current_config()
        
        # 加载缩略图
        self.lbl_status.setText("正在加载缩略图...")
        self.thumbnail_list.clear()
        
        self.loader_thread = ThumbnailLoaderThread(folder)
        self.loader_thread.progress.connect(self.on_load_progress)
        self.loader_thread.finished.connect(self.on_thumbnails_loaded)
        self.loader_thread.error.connect(self.on_load_error)
        self.loader_thread.start()
    
    def on_load_progress(self, current, total):
        self.lbl_status.setText(f"加载缩略图: {current}/{total}")
    
    def on_thumbnails_loaded(self, results):
        """缩略图加载完成（旧版兼容，逐步迁移到懒加载）"""
        self.image_paths = []
        self.thumbnails = {}
        
        # 设置缓存管理器
        self.thumbnail_cache.set_images([])
        
        for i, (path, pixmap) in enumerate(results):
            self.image_paths.append(path)
            self.thumbnails[path] = pixmap
            
            # 添加到列表 - 占位符（懒加载后更新）
            thumb_width = 176  # 图片宽度 - 20px
            scale = thumb_width / pixmap.width()
            thumb_height = int(pixmap.height() * scale)
            scaled_pixmap = pixmap.scaled(thumb_width, thumb_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            
            # 创建容器 widget
            container = QWidget()
            container.setFixedSize(196, thumb_height + 7)  # 上面 5px + 下面 2px 额外间距
            container.setStyleSheet("background-color: transparent;")
            container.setObjectName(f"thumb_container_{i}")
            
            # 创建图片 label
            img_label = QLabel(container)
            img_label.setPixmap(scaled_pixmap)
            img_label.setAlignment(Qt.AlignCenter)
            img_label.move(0, 5)  # 只上面 5px 空白
            img_label.setFixedSize(thumb_width, thumb_height)
            img_label.setObjectName(f"thumb_img_{i}")
            
            item = QListWidgetItem()
            item.setSizeHint(QSize(196, thumb_height + 12))
            item.setData(Qt.UserRole, path)  # 存储路径
            self.thumbnail_list.addItem(item)
            self.thumbnail_list.setItemWidget(item, container)
        
        # 更新缓存管理器的图片列表
        self.thumbnail_cache.set_images(self.image_paths)
        
        self.lbl_status.setText(f"共加载 {len(self.image_paths)} 张图片")
        
        # 默认选中第一张
        if self.image_paths:
            self.thumbnail_list.setCurrentRow(0)
            self.show_image(0)
    
    def on_load_error(self, error):
        self.lbl_status.setText(f"加载失败: {error}")
        QMessageBox.warning(self, "错误", f"加载图片失败：{error}")
    
    def show_context_menu(self, pos):
        """右键点击图片 - 直接裁剪不弹窗"""
        # 直接执行裁剪，不显示菜单
        self.crop_single()
    
    def on_scroll_changed(self, value):
        """滚动条值变化，触发懒加载"""
        try:
            if not hasattr(self, 'image_paths') or not self.image_paths:
                return
            self.load_visible_thumbnails()
        except Exception as e:
            pass  # 忽略滚动错误
    
    def on_thumbnail_clicked(self, item):
        """点击缩略图"""
        row = self.thumbnail_list.row(item)
        self.show_image(row)
    
    def show_image(self, index):
        """显示图片"""
        if index < 0 or index >= len(self.image_paths):
            return
        
        self.current_index = index
        path = self.image_paths[index]
        
        try:
            from image_processor import ImageProcessor
            processor = ImageProcessor()
            img = processor.load_image(path)
            
            # 显示到工作区（缩放到合适大小）
            img_width, img_height = img.size
            
            # 计算缩放比例
            label_size = self.image_label.size()
            scale = min(label_size.width() / img_width, label_size.height() / img_height)
            
            display_width = int(img_width * scale)
            display_height = int(img_height * scale)
            
            # 转为 QPixmap 显示 - 修复格式转换
            img.thumbnail((display_width * 2, display_height * 2), Image.Resampling.LANCZOS)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            data = img.tobytes('raw', 'RGB')
            qimg = QImage(data, img.width, img.height, img.width * 3, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg).scaled(display_width, display_height, Qt.KeepAspectRatio)
            
            self.current_pixmap = pixmap
            self.current_image_path = path
            self.current_image_size = (img_width, img_height)
            self.display_scale = scale  # 保存缩放比例用于坐标转换
            
            self.image_label.setPixmap(pixmap)
            # 更新状态栏显示图片信息
            processed_count = len(self.processed_indices)
            total_count = len(self.image_paths)
            self.lbl_status.setText(f"已处理：{processed_count}/{total_count}  图片：{img_width} x {img_height} | {Path(path).name}")
            
            # 更新按钮状态
            self.btn_crop_single.setEnabled(True)
            self.btn_crop_batch.setEnabled(len(self.image_paths) > 0 and self.lbl_output_dir.text() != "未选择输出目录")
            
            # 创建裁剪选区
            self.create_crop_region()
            
            # 标记已处理的状态
            if index in self.processed_indices:
                # 已处理，保持状态显示
                pass
                
        except Exception as e:
            QMessageBox.warning(self, "错误", f"加载图片失败：{e}")
    
    def create_crop_region(self):
        """创建裁剪选区 - 使用用户设置的百分比"""
        if not hasattr(self, 'current_pixmap') or not self.current_pixmap:
            return
        
        pixmap_width = self.current_pixmap.width()
        pixmap_height = self.current_pixmap.height()
        
        # 获取用户设置的百分比（10-100）
        crop_percent = self.spin_crop_ratio.value() / 100.0
        
        # 如果已应用尺寸比例，使用比例；否则根据图片方向计算
        if self.ratio_applied and self.applied_ratio is not None:
            target_ratio = self.applied_ratio
            crop_h = int(pixmap_height * crop_percent)
            crop_w = int(crop_h * target_ratio)
            if crop_w > pixmap_width * crop_percent:
                crop_w = int(pixmap_width * crop_percent)
                crop_h = int(crop_w / target_ratio)
        else:
            if pixmap_width >= pixmap_height:
                crop_size = int(pixmap_height * crop_percent)
            else:
                crop_size = int(pixmap_width * crop_percent)
            crop_w = crop_size
            crop_h = crop_size
        
        # 居中显示
        left = (pixmap_width - crop_w) // 2
        top = (pixmap_height - crop_h) // 2
        
        self.crop_rect = QRect(left, top, crop_w, crop_h)
        self.update_crop_overlay()
        print(f"Create crop rect: ({left}, {top}, {crop_w}x{crop_h}) @ {crop_percent*100:.0f}%")
    
    def update_crop_overlay(self):
        """更新裁剪覆盖层"""
        if not hasattr(self, 'current_pixmap') or not self.current_pixmap:
            return
        
        # 创建副本绘制选区
        pixmap = self.current_pixmap.copy()
        
        painter = QPainter(pixmap)
        painter.setPen(QPen(QColor(255, 0, 0), 2))
        painter.setBrush(QColor(255, 0, 0, 30))
        
        if self.crop_rect:
            painter.drawRect(self.crop_rect)
        
        painter.end()
        
        self.image_label.setPixmap(pixmap)
    
    def handle_mouse_press(self, event):
        """鼠标按下 - 整个选框都能拖拽"""
        if event.button() == Qt.LeftButton and self.crop_rect:
            # 计算 pixmap 在 label 中的偏移量
            label_size = self.image_label.size()
            pixmap_size = self.current_pixmap.size()
            
            # pixmap 在 label 中居中显示，计算偏移
            offset_x = (label_size.width() - pixmap_size.width()) // 2
            offset_y = (label_size.height() - pixmap_size.height()) // 2
            
            # 将鼠标坐标转换为 pixmap 坐标
            pos = event.pos()
            pixmap_pos = QPoint(pos.x() - offset_x, pos.y() - offset_y)
            
            # 手动检测是否在选框内（包括边框）
            in_rect = (self.crop_rect.left() <= pixmap_pos.x() <= self.crop_rect.right() and
                      self.crop_rect.top() <= pixmap_pos.y() <= self.crop_rect.bottom())
            
            print(f"Press: label_pos=({pos.x()},{pos.y()}), pixmap_pos=({pixmap_pos.x()},{pixmap_pos.y()}), rect=({self.crop_rect}), offset=({offset_x},{offset_y}), in_rect={in_rect}")
            
            if in_rect:
                self.is_dragging = True
                self.mouse_offset_x = pixmap_pos.x() - self.crop_rect.left()
                self.mouse_offset_y = pixmap_pos.y() - self.crop_rect.top()
                print(f"Start drag, offset=({self.mouse_offset_x},{self.mouse_offset_y})")
                return
        QLabel.mousePressEvent(self.image_label, event)
    
    def handle_mouse_move(self, event):
        """鼠标移动 - 整个选框都能拖拽"""
        if self.is_dragging and self.crop_rect:
            # 计算 pixmap 在 label 中的偏移量
            label_size = self.image_label.size()
            pixmap_size = self.current_pixmap.size()
            
            offset_x = (label_size.width() - pixmap_size.width()) // 2
            offset_y = (label_size.height() - pixmap_size.height()) // 2
            
            # 将鼠标坐标转换为 pixmap 坐标
            pos = event.pos()
            pixmap_pos = QPoint(pos.x() - offset_x, pos.y() - offset_y)
            
            # 计算新位置
            new_x = pixmap_pos.x() - self.mouse_offset_x
            new_y = pixmap_pos.y() - self.mouse_offset_y
            
            # 边界检查
            max_x = self.current_pixmap.width() - self.crop_rect.width()
            max_y = self.current_pixmap.height() - self.crop_rect.height()
            
            new_x = max(0, min(new_x, max_x))
            new_y = max(0, min(new_y, max_y))
            
            self.crop_rect.moveTo(new_x, new_y)
            print(f"Move to: ({new_x}, {new_y})")
            self.update_crop_overlay()
            return
        QLabel.mouseMoveEvent(self.image_label, event)
    
    def handle_mouse_release(self, event):
        """鼠标释放"""
        if self.is_dragging:
            self.is_dragging = False
            return
        QLabel.mouseReleaseEvent(self.image_label, event)
    
    def wheel_event(self, event):
        """滚轮缩放裁剪选区"""
        if not self.crop_rect or not hasattr(self, 'current_pixmap'):
            return
        
        delta = event.angleDelta().y()
        scale = 1.1 if delta > 0 else 0.9
        
        # 保持中心点缩放
        center = self.crop_rect.center()
        new_width = int(self.crop_rect.width() * scale)
        new_height = int(self.crop_rect.height() * scale)
        
        # 边界检查
        if new_width > 50 and new_width <= self.current_pixmap.width():
            if new_height > 50 and new_height <= self.current_pixmap.height():
                self.crop_rect.setSize(QSize(new_width, new_height))
                # 保持中心
                self.crop_rect.moveCenter(center)
                self.update_crop_overlay()
    
    def apply_size_to_crop(self):
        """根据目标尺寸比例调整选框"""
        if not self.crop_rect or not hasattr(self, 'current_pixmap'):
            return
        
        target_width = self.spin_width.value()
        target_height = self.spin_height.value()
        
        if target_width <= 0 or target_height <= 0:
            return
        
        # 计算目标宽高比
        target_ratio = target_width / target_height
        
        # 保存当前配置
        self.applied_ratio = target_ratio
        self.ratio_applied = True
        
        # 保持当前选框高度，调整宽度以匹配比例
        pixmap_width = self.current_pixmap.width()
        pixmap_height = self.current_pixmap.height()
        
        # 获取用户设置的百分比
        crop_percent = self.spin_crop_ratio.value() / 100.0
        
        # 选框保持当前百分比，宽度按目标比例调整
        crop_h = int(pixmap_height * crop_percent)
        crop_w = int(crop_h * target_ratio)
        
        # 如果宽度超出，反过来计算
        if crop_w > pixmap_width * crop_percent:
            crop_w = int(pixmap_width * crop_percent)
            crop_h = int(crop_w / target_ratio)
        
        # 更新选框尺寸，保持中心
        center = self.crop_rect.center()
        self.crop_rect.setSize(QSize(crop_w, crop_h))
        self.crop_rect.moveCenter(center)
        self.update_crop_overlay()
        
        self.lbl_status.setText(f"已应用尺寸比例 {target_width}:{target_height}")
        QTimer.singleShot(2000, self.reset_status_style)
    
    def center_crop_rect(self):
        """将选框居中到图片"""
        if not self.crop_rect or not hasattr(self, 'current_pixmap'):
            return
        
        pixmap_width = self.current_pixmap.width()
        pixmap_height = self.current_pixmap.height()
        
        # 计算中心位置
        center_x = pixmap_width // 2
        center_y = pixmap_height // 2
        
        # 移动选框到中心
        self.crop_rect.moveCenter(QPoint(center_x, center_y))
        self.update_crop_overlay()
    
    def reset_status_style(self):
        """重置状态栏样式"""
        self.lbl_status.setStyleSheet("color: #666; font-weight: normal; font-size: 13px;")
    
    def on_size_changed(self):
        """尺寸改变时重置比例标志"""
        self.ratio_applied = False
        self.applied_ratio = None
    
    def on_crop_ratio_changed(self):
        """选框百分比改变时，重新创建选框"""
        if hasattr(self, 'current_pixmap') and self.current_pixmap:
            self.create_crop_region()
            self.lbl_status.setText(f"选框大小：{self.spin_crop_ratio.value()}%")
            QTimer.singleShot(2000, self.reset_status_style)
    
    def select_output_dir(self):
        """选择输出目录"""
        folder = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if folder:
            self.lbl_output_dir.setText(folder)
            self.save_current_config()
            self.btn_crop_batch.setEnabled(len(self.image_paths) > 0)
    
    def crop_single(self):
        """单图裁剪"""
        if not hasattr(self, 'current_image_path'):
            return
        
        output_dir = self.lbl_output_dir.text()
        if output_dir == "未选择输出目录":
            return  # 不弹窗提示
            return
        
        try:
            from image_processor import ImageProcessor
            processor = ImageProcessor()
            
            # 将选区坐标从 pixmap 转换到原图尺寸
            scale = getattr(self, 'display_scale', 1.0)
            crop_x = int(self.crop_rect.x() / scale)
            crop_y = int(self.crop_rect.y() / scale)
            crop_w = int(self.crop_rect.width() / scale)
            crop_h = int(self.crop_rect.height() / scale)
            
            # 目标尺寸
            target_width = self.spin_width.value()
            target_height = self.spin_height.value()
            
            # 先裁剪选区，再缩放到目标尺寸
            output_path = processor.crop_and_resize(
                self.current_image_path,
                crop_x, crop_y, crop_w, crop_h,
                target_width, target_height,
                output_dir, 'jpg'
            )
            
            # 标记为已处理
            self.processed_indices.add(self.current_index)
            
            # 更新缩略图状态
            item = self.thumbnail_list.item(self.current_index)
            if item:
                item.setBackground(QColor(200, 200, 200))
            
            self.lbl_status.setText(f"已保存: {Path(output_path).name}")
            
            # 自动切换到下一张
            self.next_image()
            
        except Exception as e:
            self.lbl_status.setText(f"✗ 裁剪失败：{str(e)[:50]}")
            self.lbl_status.setStyleSheet("color: red; font-weight: bold; font-size: 14px;")
            QTimer.singleShot(2000, self.reset_status_style)
    
    def crop_batch(self):
        """批量裁剪 - 使用选框尺寸设置"""
        output_dir = self.lbl_output_dir.text()
        if output_dir == "未选择输出目录":
            return  # 不弹窗提示
        
        target_width = self.spin_width.value()
        target_height = self.spin_height.value()
        
        # 获取选框百分比设置
        crop_ratio = self.spin_crop_ratio.value() / 100.0
        
        self.save_current_config()
        
        # 禁用按钮
        self.btn_crop_batch.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(self.image_paths))
        self.progress_bar.setValue(0)
        
        from image_processor import ImageProcessor
        processor = ImageProcessor()
        
        success_count = 0
        skip_count = 0
        error_count = 0
        
        for i, path in enumerate(self.image_paths):
            try:
                # 加载图片获取尺寸
                from PIL import Image
                img = Image.open(path)
                img_width, img_height = img.size
                
                # 根据选框百分比计算裁剪尺寸
                if img_width >= img_height:
                    # 横图：按高度比例
                    crop_size = int(img_height * crop_ratio)
                else:
                    # 竖图：按宽度比例
                    crop_size = int(img_width * crop_ratio)
                
                # 计算居中裁剪区域
                crop_x = (img_width - crop_size) // 2
                crop_y = (img_height - crop_size) // 2
                
                # 执行裁剪
                output_path = processor.crop_and_resize(
                    path,
                    crop_x, crop_y, crop_size, crop_size,
                    target_width, target_height,
                    output_dir, 'jpg'
                )
                
                if output_path:
                    success_count += 1
                    self.processed_indices.add(i)
                else:
                    error_count += 1
                    
            except Exception as e:
                error_count += 1
                print(f"批量裁剪失败 {path}: {e}")
            
            self.progress_bar.setValue(i + 1)
            self.lbl_status.setText(f"处理中：{i+1}/{len(self.image_paths)}")
        
        # 更新缩略图状态
        for idx in self.processed_indices:
            item = self.thumbnail_list.item(idx)
            if item:
                item.setBackground(QColor(200, 200, 200))
        
        self.progress_bar.setVisible(False)
        self.btn_crop_batch.setEnabled(True)
        
    def prev_image(self):
        """上一张"""
        if self.current_index > 0:
            self.thumbnail_list.setCurrentRow(self.current_index - 1)
            self.show_image(self.current_index - 1)
    
    def next_image(self):
        """下一张"""
        if self.current_index < len(self.image_paths) - 1:
            self.thumbnail_list.setCurrentRow(self.current_index + 1)
            self.show_image(self.current_index + 1)
    
    def closeEvent(self, event):
        """关闭时保存配置"""
        self.save_current_config()
        event.accept()

if __name__ == '__main__':
    import sys
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import Qt
    
    # Qt 高 DPI 修复
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())














