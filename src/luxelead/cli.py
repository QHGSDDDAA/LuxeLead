import argparse
import os
from .generator import generate_ppt, DATETIME_FMT

def main():
    parser = argparse.ArgumentParser(description="LuxeLead PPT Generator - 轻奢领先竞品的PPT排版工具")
    parser.add_argument("input_folder", help="输入图片文件夹路径")
    parser.add_argument("-o", "--output", help="输出目录路径", default=None)
    parser.add_argument("-m", "--mode", choices=["folder", "prefix"],
                        default="folder", help="生成模式：folder(按文件夹) 或 prefix(按文件前缀)")
    parser.add_argument("-s", "--prefix-separator", default="_",
                        help="按文件前缀模式下的分隔符，默认 _，支持中文等任意字符")
    parser.add_argument("--prefix-cutoff-time", default=None,
                        help=f"按文件前缀模式下仅包含创建时间≥该时间的图片，格式 {DATETIME_FMT}")
    parser.add_argument("-n", "--images-per-page", type=int, default=0,
                        help="按文件夹模式下每页图片数，0 表示一页放置全部图片")
    parser.add_argument("--sort-order", choices=["asc", "desc"], default="asc",
                        help="按文件夹模式下图片排序：asc 时间正序，desc 时间倒序")
    
    args = parser.parse_args()
    
    if not os.path.isdir(args.input_folder):
        print(f"错误：输入路径 '{args.input_folder}' 不是有效的文件夹")
        return
    
    output_dir = args.output
    if output_dir is None:
        output_dir = os.path.join(os.path.expanduser("~"), "Desktop")
    
    print(f"输入文件夹: {args.input_folder}")
    print(f"输出目录: {output_dir}")
    print(f"生成模式: {'按文件夹' if args.mode == 'folder' else '按文件前缀'}")
    if args.mode == "prefix":
        print(f"前缀分隔符: {args.prefix_separator!r}")
        if args.prefix_cutoff_time:
            print(f"数据截至时间: {args.prefix_cutoff_time}")
    else:
        print(f"每页图片数 N: {args.images_per_page if args.images_per_page > 0 else '全部'}")
        print(f"图片排序: {'时间正序' if args.sort_order == 'asc' else '时间倒序'}")
    print("正在生成PPT...")

    try:
        output_file, slide_count = generate_ppt(
            args.input_folder,
            output_dir,
            args.mode,
            prefix_separator=args.prefix_separator,
            prefix_cutoff_time=args.prefix_cutoff_time,
            images_per_page=args.images_per_page,
            sort_order=args.sort_order,
        )
        print(f"成功！PPT已生成: {output_file}")
        print(f"共生成 {slide_count} 页")
    except Exception as e:
        print(f"生成失败: {str(e)}")

if __name__ == "__main__":
    main()