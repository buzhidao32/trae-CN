#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
代码审查智能体测试脚本

这个脚本提供了一个简单的界面，用于测试和演示代码审查智能体的主要功能。
您可以通过命令行参数指定要执行的测试类型，或直接运行查看所有测试结果。
"""

import os
import sys
import subprocess
import time
from datetime import datetime

# 获取当前目录
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
AGENT_SCRIPT = os.path.join(CURRENT_DIR, "code_review_agent.py")
EXAMPLE_FILE = os.path.join(CURRENT_DIR, "example_code.py")


def print_color(text, color_code):
    """打印带颜色的文本"""
    print(f"\033[{color_code}m{text}\033[0m")


def print_success(text):
    """打印成功信息"""
    print_color(f"✓ {text}", "32")  # 绿色


def print_error(text):
    """打印错误信息"""
    print_color(f"✗ {text}", "31")  # 红色


def print_warning(text):
    """打印警告信息"""
    print_color(f"! {text}", "33")  # 黄色


def print_info(text):
    """打印信息"""
    print_color(f"ℹ {text}", "36")  # 青色


def print_header(text):
    """打印标题"""
    print_color(f"\n{'='*60}\n{text}\n{'='*60}", "34")  # 蓝色


def run_command(command, timeout=60):
    """运行命令并返回输出和退出码"""
    print_info(f"执行命令: {' '.join(command)}")
    
    try:
        start_time = time.time()
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            cwd=CURRENT_DIR
        )
        end_time = time.time()
        
        # 打印执行时间
        print_info(f"命令执行时间: {end_time - start_time:.2f}秒")
        
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        print_error(f"命令执行超时 ({timeout}秒)")
        return "", "Command timed out", 1
    except Exception as e:
        print_error(f"命令执行异常: {e}")
        return "", str(e), 1


def test_single_file_review():
    """测试单文件审查功能"""
    print_header("测试单文件审查功能")
    
    # 测试JSON格式输出
    command = [
        sys.executable,
        AGENT_SCRIPT,
        "--file", EXAMPLE_FILE,
        "--format", "json"
    ]
    
    stdout, stderr, returncode = run_command(command)
    
    if returncode == 0:
        print_success("单文件审查(JSON格式)测试通过")
        # 检查输出是否包含预期的JSON结构
        if "code_quality" in stdout and "potential_issues" in stdout:
            print_success("输出包含预期的JSON结构")
        else:
            print_warning("输出格式可能不符合预期，请检查")
    else:
        print_error("单文件审查测试失败")
        if stderr:
            print_error(f"错误信息: {stderr}")
    
    # 测试文本格式输出
    command = [
        sys.executable,
        AGENT_SCRIPT,
        "--file", EXAMPLE_FILE,
        "--format", "text"
    ]
    
    stdout, stderr, returncode = run_command(command)
    
    if returncode == 0:
        print_success("单文件审查(文本格式)测试通过")
    else:
        print_error("单文件审查(文本格式)测试失败")
        if stderr:
            print_error(f"错误信息: {stderr}")


def test_directory_review():
    """测试目录审查功能"""
    print_header("测试目录审查功能")
    
    # 测试审查当前目录下的Python文件
    command = [
        sys.executable,
        AGENT_SCRIPT,
        "--dir", CURRENT_DIR,
        "--extensions", ".py",
        "--workers", "2",
        "--format", "text"
    ]
    
    stdout, stderr, returncode = run_command(command)
    
    if returncode == 0:
        print_success("目录审查测试通过")
    else:
        print_error("目录审查测试失败")
        if stderr:
            print_error(f"错误信息: {stderr}")


def test_cache_functionality():
    """测试缓存功能"""
    print_header("测试缓存功能")
    
    # 第一次运行(生成缓存)
    print_info("第一次运行(生成缓存)...")
    command = [
        sys.executable,
        AGENT_SCRIPT,
        "--file", EXAMPLE_FILE,
        "--format", "json"
    ]
    
    start_time = time.time()
    stdout1, stderr1, returncode1 = run_command(command)
    first_run_time = time.time() - start_time
    
    # 第二次运行(使用缓存)
    print_info("第二次运行(使用缓存)...")
    start_time = time.time()
    stdout2, stderr2, returncode2 = run_command(command)
    second_run_time = time.time() - start_time
    
    if returncode1 == 0 and returncode2 == 0:
        # 检查第二次运行是否更快(缓存生效)
        if second_run_time < first_run_time * 0.5:  # 至少快50%
            print_success("缓存功能测试通过")
            print_info(f"第一次运行时间: {first_run_time:.2f}秒")
            print_info(f"第二次运行时间: {second_run_time:.2f}秒")
            print_info(f"性能提升: {(first_run_time/second_run_time-1)*100:.1f}%")
        else:
            print_warning("缓存可能未生效，第二次运行没有明显变快")
            print_info(f"第一次运行时间: {first_run_time:.2f}秒")
            print_info(f"第二次运行时间: {second_run_time:.2f}秒")
    else:
        print_error("缓存功能测试失败")


def test_git_review():
    """测试Git仓库审查功能"""
    print_header("测试Git仓库审查功能")
    
    # 检查当前目录是否是Git仓库
    is_git_repo = os.path.exists(os.path.join(CURRENT_DIR, ".git"))
    
    if not is_git_repo:
        print_warning("当前目录不是Git仓库，跳过Git审查测试")
        print_info("您可以将代码放入Git仓库后再次测试此功能")
        return
    
    command = [
        sys.executable,
        AGENT_SCRIPT,
        "--repo", CURRENT_DIR,
        "--branch", "main",
        "--format", "text"
    ]
    
    stdout, stderr, returncode = run_command(command)
    
    if returncode == 0:
        print_success("Git仓库审查测试通过")
    else:
        print_error("Git仓库审查测试失败")
        if stderr:
            print_error(f"错误信息: {stderr}")


def test_output_file():
    """测试输出到文件功能"""
    print_header("测试输出到文件功能")
    
    # 创建临时输出文件
    output_file = os.path.join(CURRENT_DIR, f"test_output_{datetime.now().strftime('%Y%m%d%H%M%S')}.json")
    
    command = [
        sys.executable,
        AGENT_SCRIPT,
        "--file", EXAMPLE_FILE,
        "--output", output_file
    ]
    
    stdout, stderr, returncode = run_command(command)
    
    if returncode == 0 and os.path.exists(output_file) and os.path.getsize(output_file) > 0:
        print_success(f"输出到文件测试通过，文件已创建: {output_file}")
        # 清理临时文件
        try:
            os.remove(output_file)
            print_info(f"临时文件已删除: {output_file}")
        except:
            pass
    else:
        print_error("输出到文件测试失败")
        if stderr:
            print_error(f"错误信息: {stderr}")


def show_help():
    """显示帮助信息"""
    print("代码审查智能体测试脚本")
    print("使用方法:")
    print("  python test_agent.py [test_type]")
    print()
    print("测试类型:")
    print("  all             运行所有测试")
    print("  file            测试单文件审查功能")
    print("  dir             测试目录审查功能")
    print("  cache           测试缓存功能")
    print("  git             测试Git仓库审查功能")
    print("  output          测试输出到文件功能")
    print()
    print("示例:")
    print("  python test_agent.py file")


def main():
    """主函数"""
    # 检查代码审查智能体脚本是否存在
    if not os.path.exists(AGENT_SCRIPT):
        print_error(f"未找到代码审查智能体脚本: {AGENT_SCRIPT}")
        print_info("请确保在正确的目录下运行此测试脚本")
        sys.exit(1)
    
    # 检查示例文件是否存在
    if not os.path.exists(EXAMPLE_FILE):
        print_warning(f"未找到示例文件: {EXAMPLE_FILE}")
        print_info("将使用代码审查智能体脚本自身作为测试文件")
        global EXAMPLE_FILE
        EXAMPLE_FILE = AGENT_SCRIPT
    
    # 解析命令行参数
    test_type = "all"
    if len(sys.argv) > 1:
        test_type = sys.argv[1].lower()
    
    if test_type == "help" or test_type == "-h" or test_type == "--help":
        show_help()
        sys.exit(0)
    
    print_header(f"代码审查智能体测试 - {test_type}")
    
    # 运行指定的测试
    if test_type == "all":
        test_single_file_review()
        test_directory_review()
        test_cache_functionality()
        test_git_review()
        test_output_file()
    elif test_type == "file":
        test_single_file_review()
    elif test_type == "dir":
        test_directory_review()
    elif test_type == "cache":
        test_cache_functionality()
    elif test_type == "git":
        test_git_review()
    elif test_type == "output":
        test_output_file()
    else:
        print_error(f"未知的测试类型: {test_type}")
        show_help()
        sys.exit(1)
    
    print_header("测试完成")


if __name__ == "__main__":
    main()