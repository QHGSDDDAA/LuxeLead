from .version import VERSION as __version__
__author__ = "LuxeLead Team"
__description__ = "LuxeLead PPT Generator - 轻奢领先竞品的PPT排版工具"

from .generator import generate_ppt, get_image_files
from .layout import add_images_to_slide

__all__ = ["generate_ppt", "get_image_files", "add_images_to_slide"]