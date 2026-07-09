import os
import sys
from pptx.util import Inches

from .image_formats import open_image_for_ppt, register_heic_support, save_rgb_jpeg

register_heic_support()

EMU_PER_PIXEL = 9525
SLIDE_WIDTH = Inches(13.333)
SLIDE_HEIGHT = Inches(7.5)

# 全局变量缓存模型，避免重复加载
_yolo_model = None

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_MODULE_DIR, "..", ".."))


def get_resource_path(relative_path):
    """
    获取资源文件的绝对路径，支持打包后的环境
    """
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(os.path.join(sys._MEIPASS, relative_path))
    else:
        candidates.extend([
            os.path.join(_MODULE_DIR, relative_path),
            os.path.join(_PROJECT_ROOT, relative_path),
        ])
    try:
        candidates.append(os.path.join(sys._MEIPASS, relative_path))
    except Exception:
        pass

    for path in candidates:
        if os.path.exists(path):
            return path

    base_path = getattr(sys, "_MEIPASS", _MODULE_DIR)
    return os.path.join(base_path, relative_path)


def find_yolov8_model_path():
    """查找 YOLOv8 模型文件，兼容源码运行与 PyInstaller 打包。"""
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(os.path.join(sys._MEIPASS, "yolov8n.pt"))
    else:
        candidates.extend([
            os.path.join(_MODULE_DIR, "yolov8n.pt"),
            os.path.join(_PROJECT_ROOT, "yolov8n.pt"),
        ])
    try:
        candidates.append(os.path.join(sys._MEIPASS, "yolov8n.pt"))
    except Exception:
        pass
    candidates.extend([
        os.path.join(os.getcwd(), "yolov8n.pt"),
        "yolov8n.pt",
    ])

    seen = set()
    for path in candidates:
        if not path:
            continue
        norm = os.path.normpath(path)
        if norm in seen:
            continue
        seen.add(norm)
        if os.path.isfile(norm):
            return norm
    return None


def check_yolov8_available():
    """
    检查 YOLOv8 是否可用
    返回: (是否可用, 错误信息)
    """
    global _yolo_model
    try:
        if _yolo_model is not None:
            return True, None
        
        from ultralytics import YOLO

        model_path = find_yolov8_model_path()
        if model_path is None:
            return False, "YOLOv8 模型文件 yolov8n.pt 未找到"
        
        # 尝试加载模型
        _yolo_model = YOLO(model_path)
        return True, None
        
    except ImportError as e:
        return False, f"YOLOv8 未安装: {str(e)}"
    except Exception as e:
        return False, f"YOLOv8 初始化失败: {str(e)}"


def crop_image_by_yolov8(img):
    """
    使用YOLOv8进行人物检测并裁剪
    如果YOLOv8不可用，返回(None, None)
    返回: (裁剪后的图片, 裁剪信息字典) 或 (None, None)
    """
    global _yolo_model
    try:
        from ultralytics import YOLO
        
        if _yolo_model is None:
            model_path = find_yolov8_model_path()
            if model_path is None:
                return None, {'success': False, 'reason': 'YOLOv8 模型文件 yolov8n.pt 未找到'}

            _yolo_model = YOLO(model_path)
        
        results = _yolo_model(img)
        
        boxes = []
        detected_objects = []
        class_names = {0: 'person', 26: 'handbag'}
        
        for result in results:
            for box in result.boxes:
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                if conf > 0.5 and cls in [0, 26]:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    boxes.append((x1, y1, x2, y2))
                    detected_objects.append({
                        'class': class_names.get(cls, f'class_{cls}'),
                        'confidence': round(conf, 2),
                        'box': (int(x1), int(y1), int(x2), int(y2))
                    })
        
        if not boxes:
            return None, {'success': False, 'reason': '未检测到人物', 'detected_objects': []}
        
        min_x = min(box[0] for box in boxes)
        min_y = min(box[1] for box in boxes)
        max_x = max(box[2] for box in boxes)
        max_y = max(box[3] for box in boxes)
        
        width, height = img.size
        
        crop_width = max_x - min_x
        crop_height = max_y - min_y
        
        min_crop_width = max(crop_width, width * 0.4)
        min_crop_height = max(crop_height, height * 0.5)
        
        center_x = (min_x + max_x) // 2
        center_y = (min_y + max_y) // 2
        
        half_width = min_crop_width // 2
        half_height = min_crop_height // 2
        
        new_min_x = max(0, int(center_x - half_width) - 10)
        new_max_x = min(width - 1, int(center_x + half_width) + 10)
        new_min_y = max(0, int(center_y - half_height) - 10)
        new_max_y = min(height - 1, int(center_y + half_height) + 10)
        
        if new_min_x >= new_max_x or new_min_y >= new_max_y:
            return None, {'success': False, 'reason': '裁剪区域无效', 'detected_objects': detected_objects}
        
        cropped_img = img.crop((new_min_x, new_min_y, new_max_x, new_max_y))
        
        info = {
            'success': True,
            'detected_objects': detected_objects,
            'original_size': (width, height),
            'crop_area': (new_min_x, new_min_y, new_max_x, new_max_y),
            'crop_size': (new_max_x - new_min_x, new_max_y - new_min_y),
            'scale': (round((new_max_x - new_min_x)/width*100, 1), round((new_max_y - new_min_y)/height*100, 1)),
            'method': 'yolov8'
        }
        
        return cropped_img, info
        
    except ImportError as e:
        return None, {'success': False, 'reason': f'YOLOv8未安装: {str(e)}'}
    except Exception as e:
        return None, {'success': False, 'reason': f'YOLOv8错误: {str(e)}'}

def fixed_height_flow_layout(page_w, page_h, ratios, padding=10, gap=8):
    """
    固定高度流式布局算法（Fixed-Height Flow Layout）6月份
    标准行业逻辑：等高、等比宽、自动换行、全部放进容器
    参数:
        page_w: 页面宽度(EMU)
        page_h: 页面高度(EMU)
        ratios: 所有图片的宽高比列表 [w/h, ...]
        padding: 页面四周留白(像素)
        gap: 图片之间的间距(像素)
    返回: (最优统一高度H, 所有图片的[(x, y, w, h), ...])
    """
    avail_w = page_w - 2 * padding
    avail_h = page_h - 2 * padding

    current_h = avail_h
    best_h = current_h
    best_layout = []

    for _ in range(100):
        x = padding
        y = padding
        layout = []

        for ratio in ratios:
            w = ratio * current_h
            h = current_h

            if x + w > page_w - padding:
                x = padding
                y += h + gap

            layout.append((x, y, w, h))
            x += w + gap

        total_h = y + current_h + padding
        if total_h <= page_h:
            best_h = current_h
            best_layout = layout
            break
        else:
            current_h *= 0.95

    if not best_layout and ratios:
        current_h = avail_h * 0.5
        x = padding
        y = padding
        best_layout = []
        for ratio in ratios:
            w = ratio * current_h
            h = current_h
            if x + w > page_w - padding:
                x = padding
                y += h + gap
            best_layout.append((x, y, w, h))
            x += w + gap
        best_h = current_h

    return best_h, best_layout

def add_images_to_slide(slide, image_paths, slide_w, slide_h, crop=False, crop_output_dir=None, log_callback=None):
    """
    使用固定高度流式布局算法（6月份）将图片添加到幻灯片
    """
    import tempfile
    
    image_count = len(image_paths)
    if image_count == 0:
        return
    
    images_info = []
    temp_files = []
    crop_logs = []
    
    for path in image_paths:
        try:
            img = open_image_for_ppt(path)
            filename = os.path.basename(path)
            
            original_img = img.copy()
            cropped = False
            crop_info = None
            
            if crop:
                cropped_img, crop_info = crop_image_by_yolov8(img)
                if cropped_img is not None:
                    img = cropped_img
                    cropped = True
            
            w, h = img.size
            
            if crop:
                if crop_info and crop_info['success']:
                    log_msg = f"✅ [{filename}] 裁剪成功"
                    log_msg += f" | 方法: {crop_info.get('method', 'unknown')}"
                    log_msg += f" | 原图: {crop_info['original_size'][0]}x{crop_info['original_size'][1]}"
                    log_msg += f" | 裁剪后: {crop_info['crop_size'][0]}x{crop_info['crop_size'][1]}"
                    log_msg += f" | 缩放: {crop_info['scale'][0]}% x {crop_info['scale'][1]}%"
                    
                    if 'warning' in crop_info:
                        log_msg += f" | 警告: {crop_info['warning']}"
                    
                    if crop_info['detected_objects']:
                        objects_info = ", ".join([f"{obj['class']}({obj['confidence']})" for obj in crop_info['detected_objects']])
                        log_msg += f" | 检测: {objects_info}"
                    
                    crop_logs.append(log_msg)
                    if log_callback:
                        log_callback(log_msg)
                else:
                    reason = crop_info['reason'] if crop_info else '未知错误'
                    log_msg = f"❌ [{filename}] 裁剪失败: {reason}"
                    crop_logs.append(log_msg)
                    if log_callback:
                        log_callback(log_msg)
            
            if cropped and crop_output_dir:
                os.makedirs(crop_output_dir, exist_ok=True)
                name, ext = os.path.splitext(filename)
                crop_filename = f"cropped_{name}{ext}"
                crop_path = os.path.join(crop_output_dir, crop_filename)
                
                save_rgb_jpeg(img, crop_path)
                
                save_msg = f"📸 [{filename}] 裁剪图片已保存: {crop_path}"
                crop_logs.append(save_msg)
                if log_callback:
                    log_callback(save_msg)
            
            temp_fd, temp_path = tempfile.mkstemp(suffix='.jpg')
            os.close(temp_fd)
            
            save_rgb_jpeg(img, temp_path)
            
            final_w, final_h = img.size
            ratio = final_w / final_h
            
            temp_files.append(temp_path)
            images_info.append((temp_path, ratio))
            img.close()
            original_img.close()
            
        except Exception as e:
            error_msg = f"⚠️ [{os.path.basename(path)}] 处理失败: {str(e)}"
            crop_logs.append(error_msg)
            if log_callback:
                log_callback(error_msg)
            continue
    
    if not images_info:
        no_image_msg = "警告: 没有可以添加的图片！"
        crop_logs.append(no_image_msg)
        if log_callback:
            log_callback(no_image_msg)
        for f in temp_files:
            try:
                os.remove(f)
            except:
                pass
        return
    
    ratios = [img[1] for img in images_info]
    paths = [img[0] for img in images_info]
    
    slide_w_px = slide_w / EMU_PER_PIXEL
    slide_h_px = slide_h / EMU_PER_PIXEL
    
    best_h_px, layout = fixed_height_flow_layout(
        page_w=slide_w_px,
        page_h=slide_h_px,
        ratios=ratios,
        padding=5,
        gap=5
    )
    
    for i, (path, ratio) in enumerate(images_info):
        x, y, w, h = layout[i]
        
        left = int(x * EMU_PER_PIXEL)
        top = int(y * EMU_PER_PIXEL)
        width = int(w * EMU_PER_PIXEL)
        height = int(h * EMU_PER_PIXEL)
        
        try:
            slide.shapes.add_picture(path, left, top, width=width, height=height)
        except Exception as e:
            error_msg = f"⚠️ [添加图片失败] {os.path.basename(path)}: {str(e)}"
            crop_logs.append(error_msg)
            if log_callback:
                log_callback(error_msg)
    
    for f in temp_files:
        try:
            os.remove(f)
        except:
            pass
    
    return crop_logs