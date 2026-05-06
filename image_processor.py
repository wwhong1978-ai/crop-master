# 图片处理模块
import os
from pathlib import Path
from PIL import Image
from datetime import datetime

class ImageProcessor:
    def __init__(self):
        self.supported_formats = ['.jpg', '.jpeg', '.png', '.bmp']
    
    def scan_images(self, folder_path: str) -> list:
        """扫描文件夹中的图片"""
        paths = []
        folder = Path(folder_path)
        
        if not folder.exists():
            raise FileNotFoundError(f"文件夹不存在：{folder_path}")
        
        for ext in self.supported_formats:
            for img_path in folder.glob(f'*{ext}'):
                paths.append(str(img_path))
        
        # 也支持大写扩展名
        for ext in [e.upper() for e in self.supported_formats]:
            for img_path in folder.glob(f'*{ext}'):
                if str(img_path) not in paths:
                    paths.append(str(img_path))
        
        return sorted(paths)
    
    def load_image(self, path: str) -> Image.Image:
        """加载图片"""
        img = Image.open(path)
        # 统一转为 RGB 模式
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        return img
    
    def get_image_info(self, path: str) -> dict:
        """获取图片信息"""
        try:
            img = self.load_image(path)
            return {
                'width': img.width,
                'height': img.height,
                'size': img.size,
                'mode': img.mode
            }
        except Exception as e:
            return {'error': str(e)}
    
    def crop_image(self, path: str, left: int, top: int, width: int, height: int, 
                   output_dir: str, output_format: str = 'jpg') -> str:
        """裁剪图片"""
        img = self.load_image(path)
        
        # 计算裁剪区域
        right = left + width
        bottom = top + height
        
        # 确保不超出图片边界
        if right > img.width:
            right = img.width
            left = right - width
        if bottom > img.height:
            bottom = img.height
            top = bottom - height
        if left < 0:
            left = 0
        if top < 0:
            top = 0
        
        # 执行裁剪
        cropped = img.crop((left, top, right, bottom))
        
        # 生成输出文件名：原文件名_时间戳.jpg
        original_name = Path(path).stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = f"{original_name}_{timestamp}.{output_format}"
        
        # 保存
        output_path = Path(output_dir) / output_name
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if output_format.lower() in ['jpg', 'jpeg']:
            cropped.save(output_path, "JPEG", quality=90)
        else:
            cropped.save(output_path, "PNG")
        
        return str(output_path)
    
    def crop_and_resize(self, path: str, left: int, top: int, width: int, height: int,
                        target_width: int, target_height: int,
                        output_dir: str, output_format: str = 'jpg') -> str:
        """裁剪图片并缩放到目标尺寸"""
        img = self.load_image(path)
        print(f"crop_and_resize: 原图={img.width}x{img.height}, 裁剪=({left},{top},{width}x{height}), 目标={target_width}x{target_height}")
        
        # 计算裁剪区域
        right = left + width
        bottom = top + height
        
        # 确保不超出图片边界
        if right > img.width:
            right = img.width
            left = right - width
        if bottom > img.height:
            bottom = img.height
            top = bottom - height
        if left < 0:
            left = 0
        if top < 0:
            top = 0
        
        # 执行裁剪
        cropped = img.crop((left, top, right, bottom))
        print(f"crop_and_resize: 裁剪后={cropped.width}x{cropped.height}")
        
        # 强制缩放到目标尺寸
        resized = cropped.resize((target_width, target_height), Image.Resampling.LANCZOS)
        print(f"crop_and_resize: 缩放后={resized.width}x{resized.height}")
        
        # 生成输出文件名：原文件名_时间戳.jpg
        original_name = Path(path).stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = f"{original_name}_{timestamp}.{output_format}"
        
        # 保存
        output_path = Path(output_dir) / output_name
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if output_format.lower() in ['jpg', 'jpeg']:
            resized.save(output_path, "JPEG", quality=90)
        else:
            resized.save(output_path, "PNG")
        
        print(f"crop_and_resize: 已保存到 {output_path}")
        return str(output_path)
    
    def auto_crop_center(self, path: str, target_width: int, target_height: int,
                        output_dir: str, output_format: str = 'jpg') -> tuple:
        """
        自动居中裁剪并缩放到目标尺寸（100% 选框）
        返回：(success, output_path_or_error_message)
        """
        return self.crop_with_ratio(path, target_width, target_height, output_dir, output_format, crop_ratio=100)
    
    def crop_with_ratio(self, path: str, target_width: int, target_height: int,
                       output_dir: str, output_format: str = 'jpg',
                       crop_ratio: float = 90) -> tuple:
        """
        按指定选框百分比居中裁剪并缩放到目标尺寸
        crop_ratio: 选框大小百分比（10-100），默认 90
        返回：(success, output_path_or_error_message)
        """
        try:
            img = self.load_image(path)
            
            # 计算目标宽高比
            target_ratio = target_width / target_height
            
            # 计算选框百分比
            crop_percent = crop_ratio / 100.0
            
            # 根据图片方向决定裁剪策略（使用选框百分比）
            if img.width >= img.height:
                # 横图：按高度的 crop_percent 计算
                crop_h = int(img.height * crop_percent)
                crop_w = int(crop_h * target_ratio)
                # 如果宽度超出，反过来计算
                if crop_w > img.width * crop_percent:
                    crop_w = int(img.width * crop_percent)
                    crop_h = int(crop_w / target_ratio)
            else:
                # 竖图：按宽度的 crop_percent 计算
                crop_w = int(img.width * crop_percent)
                crop_h = int(crop_w / target_ratio)
                # 如果高度超出，反过来计算
                if crop_h > img.height * crop_percent:
                    crop_h = int(img.height * crop_percent)
                    crop_w = int(crop_h * target_ratio)
            
            # 居中
            left = (img.width - crop_w) // 2
            top = (img.height - crop_h) // 2
            
            # 执行裁剪
            cropped = img.crop((left, top, left + crop_w, top + crop_h))
            
            # 缩放到目标尺寸
            resized = cropped.resize((target_width, target_height), Image.Resampling.LANCZOS)
            
            # 生成输出文件名
            original_name = Path(path).stem
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_name = f"{original_name}_{timestamp}.{output_format}"
            
            output_path = Path(output_dir) / output_name
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            if output_format.lower() in ['jpg', 'jpeg']:
                resized.save(output_path, "JPEG", quality=90)
            else:
                resized.save(output_path, "PNG")
            
            return (True, str(output_path))
            
        except Exception as e:
            return (False, str(e))


    def create_thumbnail(self, path: str, size: tuple = (100, 100)) -> Image.Image:
        """创建缩略图"""
        img = self.load_image(path)
        img.thumbnail(size, Image.Resampling.LANCZOS)
        return img