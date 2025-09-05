import os
import sys
import argparse
import git
import openai
import json
import time
import concurrent.futures
import hashlib
import logging
from datetime import datetime
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Optional, Any, Set, Tuple

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("code_review.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("code_review_agent")

class CodeReviewConfig(BaseModel):
    model: str = "gpt-4o"
    temperature: float = 0.2
    max_tokens: int = 4096
    api_base: Optional[str] = None
    retry_count: int = 3
    retry_delay: int = 2
    concurrent_workers: int = 2
    cache_dir: str = ".cache"
    
    @field_validator('temperature')
    def validate_temperature(cls, v):
        if not (0 <= v <= 2):
            raise ValueError("温度必须在0到2之间")
        return v
    
    @field_validator('retry_count')
    def validate_retry_count(cls, v):
        if v < 0:
            raise ValueError("重试次数不能为负数")
        return v
    
    @field_validator('concurrent_workers')
    def validate_concurrent_workers(cls, v):
        if v < 1:
            raise ValueError("并发工作线程至少为1")
        return v

# 支持的编程语言及其文件扩展名
SUPPORTED_LANGUAGES = {
    "python": [".py"],
    "javascript": [".js", ".jsx"],
    "typescript": [".ts", ".tsx"],
    "java": [".java"],
    "csharp": [".cs"],
    "go": [".go"],
    "rust": [".rs"],
    "cpp": [".cpp", ".cc", ".cxx", ".c++", ".h", ".hpp"],
    "c": [".c", ".h"],
    "php": [".php"],
    "ruby": [".rb"],
    "swift": [".swift"],
    "kotlin": [".kt"],
    "html": [".html", ".htm"],
    "css": [".css"],
    "scss": [".scss"],
    "json": [".json"],
    "yaml": [".yaml", ".yml"],
    "markdown": [".md"],
    "sql": [".sql"]
}

# 语言特定的审查提示
LANGUAGE_SPECIFIC_PROMPTS = {
    "python": "特别注意PEP 8规范的遵守情况，包括缩进、命名约定、导入顺序等。检查是否有使用Python 3的新特性来简化代码。",
    "javascript": "特别注意ES6+特性的使用，检查是否有回调地狱问题，以及异步代码的处理方式。",
    "typescript": "特别注意类型定义的完整性和准确性，检查是否有未使用的变量或导入。",
    "java": "特别注意异常处理和资源管理，检查是否有内存泄漏风险。",
    "csharp": "特别注意空引用问题，检查是否有适当的null检查。",
    "go": "特别注意错误处理方式，检查是否有goroutine泄漏风险。"
}

class CodeReviewer:
    def __init__(self, config: CodeReviewConfig):
        self.config = config
        # 加载环境变量
        load_dotenv()
        # 设置OpenAI API密钥和基础URL
        openai.api_key = os.getenv("OPENAI_API_KEY")
        
        if not openai.api_key:
            raise ValueError("请设置OPENAI_API_KEY环境变量")
        
        # 设置API基础URL（如果提供）
        if config.api_base:
            openai.api_base = config.api_base
        elif os.getenv("OPENAI_API_BASE"):
            openai.api_base = os.getenv("OPENAI_API_BASE")
        
        # 初始化缓存目录
        os.makedirs(config.cache_dir, exist_ok=True)
    
    def _get_file_language(self, file_path: str) -> Optional[str]:
        """根据文件扩展名判断编程语言"""
        ext = os.path.splitext(file_path)[1].lower()
        for lang, extensions in SUPPORTED_LANGUAGES.items():
            if ext in extensions:
                return lang
        return None
    
    def _get_cache_key(self, content: str, prompt: str) -> str:
        """生成缓存键"""
        combined = f"{content}\n---\n{prompt}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    def _get_cached_result(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """获取缓存的审查结果"""
        cache_file = os.path.join(self.config.cache_dir, f"{cache_key}.json")
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"读取缓存文件失败: {e}")
        return None
    
    def _cache_result(self, cache_key: str, result: Dict[str, Any]) -> None:
        """缓存审查结果"""
        cache_file = os.path.join(self.config.cache_dir, f"{cache_key}.json")
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"缓存结果失败: {e}")
    
    def _call_openai_api(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """调用OpenAI API并处理重试逻辑"""
        for attempt in range(self.config.retry_count):
            try:
                response = openai.chat.completions.create(
                    model=self.config.model,
                    messages=messages,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                    response_format={"type": "json_object"}
                )
                
                # 解析JSON响应
                try:
                    return json.loads(response.choices[0].message.content)
                except json.JSONDecodeError:
                    logger.error(f"API返回的内容不是有效的JSON: {response.choices[0].message.content}")
                    return {"error": "API返回的内容格式无效"}
                    
            except openai.RateLimitError:
                logger.warning(f"达到API速率限制，{self.config.retry_delay}秒后重试... (尝试 {attempt+1}/{self.config.retry_count})")
                time.sleep(self.config.retry_delay * (2 ** attempt))  # 指数退避
            except openai.APIError as e:
                logger.warning(f"API错误: {e}, {self.config.retry_delay}秒后重试... (尝试 {attempt+1}/{self.config.retry_count})")
                time.sleep(self.config.retry_delay * (2 ** attempt))
            except Exception as e:
                logger.error(f"调用API时发生未预期错误: {e}")
                return {"error": str(e)}
        
        logger.error(f"达到最大重试次数 {self.config.retry_count}，API调用失败")
        return {"error": f"达到最大重试次数 {self.config.retry_count}"}
    
    def review_file(self, file_path: str, file_content: str) -> Dict[str, Any]:
        """审查单个文件"""
        logger.info(f"开始审查文件: {file_path}")
        
        # 判断文件语言
        language = self._get_file_language(file_path)
        language_prompt = LANGUAGE_SPECIFIC_PROMPTS.get(language, "")
        
        # 构建提示词
        prompt = f"""你是一名经验丰富的代码审查专家，请审查以下代码文件：

文件路径：{file_path}
{"编程语言：" + language if language else ""}

代码内容：
```
{file_content}
```

请从以下几个方面进行审查：
1. 代码质量和可读性
2. 潜在的bug和逻辑问题
3. 性能优化建议
4. 安全性考虑
5. 最佳实践符合性
6. 代码复杂度分析
7. 代码重复检测
8. 代码风格一致性

{language_prompt}

请提供具体的反馈和改进建议，返回格式必须是JSON对象，包含以下字段：
- code_quality: {"rating": 评分(1-5), "comments": [评论列表]}
- potential_issues: [{"line": 行号, "description": 问题描述, "severity": "low|medium|high", "suggestion": 改进建议}]
- performance_suggestions: [性能优化建议列表]
- security_considerations: [安全考虑建议列表]
- best_practices: [最佳实践建议列表]
- complexity_analysis: {"score": 复杂度分数, "hotspots": [热点代码行号列表]}
- code_duplication: [{"line": 行号, "description": 重复代码描述}]
- style_consistency: {"rating": 评分(1-5), "issues": [风格问题列表]}
- summary: 总体总结

请确保返回的JSON可以被正确解析，不要包含任何JSON之外的内容。"""
        
        # 检查缓存
        cache_key = self._get_cache_key(file_content, prompt)
        cached_result = self._get_cached_result(cache_key)
        if cached_result:
            logger.info(f"使用缓存结果: {file_path}")
            return cached_result
        
        # 调用API
        messages = [
            {"role": "system", "content": "你是一名经验丰富的代码审查专家，擅长多语言代码分析和优化。"},
            {"role": "user", "content": prompt}
        ]
        
        start_time = time.time()
        result = self._call_openai_api(messages)
        end_time = time.time()
        
        logger.info(f"文件审查完成: {file_path}, 耗时: {end_time - start_time:.2f}秒")
        
        # 缓存结果（如果没有错误）
        if "error" not in result:
            self._cache_result(cache_key, result)
        
        return result
    
    def review_git_diff(self, repo_path: str, branch: str = "main", commit_range: Optional[str] = None) -> Dict[str, Any]:
        """审查Git仓库中的差异"""
        logger.info(f"开始审查Git仓库差异: {repo_path}, 基准分支: {branch}")
        
        try:
            repo = git.Repo(repo_path)
            
            # 构建差异查询
            if commit_range:
                diff_spec = commit_range
            else:
                diff_spec = f"{branch}..HEAD"
            
            # 获取差异
            diff = repo.git.diff(diff_spec)
            
            if not diff:
                return {"message": "没有找到差异"}
            
            # 分析变更的文件
            changed_files = []
            for line in diff.split('\n'):
                if line.startswith('diff --git'):
                    parts = line.split(' ')
                    if len(parts) >= 3:
                        file_path = parts[3].lstrip('a/')
                        changed_files.append(file_path)
            
            prompt = f"""你是一名经验丰富的代码审查专家，请审查以下Git差异：

差异范围：{diff_spec}
变更文件数：{len(changed_files)}
变更文件列表：{', '.join(changed_files[:10])}{'...' if len(changed_files) > 10 else ''}

差异内容：
```
{diff[:8000]}  # 限制差异大小，避免超出token限制
{'... 差异内容过长，已截断 ...' if len(diff) > 8000 else ''}
```

请从以下几个方面进行审查：
1. 代码质量和可读性
2. 潜在的bug和逻辑问题
3. 性能优化建议
4. 安全性考虑
5. 最佳实践符合性
6. 总体设计合理性
7. 测试覆盖建议

请提供具体的反馈和改进建议，返回格式必须是JSON对象，包含以下字段：
- summary: 总体总结
- file_reviews: [{"file_path": 文件路径, "issues": 问题数量, "highlights": [亮点列表]}]
- critical_issues: [{"file_path": 文件路径, "line": 行号, "description": 问题描述, "severity": "critical"}]
- improvements: [改进建议列表]
- test_recommendations: [测试建议列表]
- rating: 总体评分(1-5)

请确保返回的JSON可以被正确解析，不要包含任何JSON之外的内容。"""
            
            # 检查缓存
            cache_key = self._get_cache_key(diff, prompt)
            cached_result = self._get_cached_result(cache_key)
            if cached_result:
                logger.info(f"使用缓存结果: Git差异 {diff_spec}")
                return cached_result
            
            # 调用API
            messages = [
                {"role": "system", "content": "你是一名经验丰富的代码审查专家，擅长分析代码变更和版本差异。"},
                {"role": "user", "content": prompt}
            ]
            
            start_time = time.time()
            result = self._call_openai_api(messages)
            end_time = time.time()
            
            logger.info(f"Git差异审查完成: {repo_path}, 耗时: {end_time - start_time:.2f}秒")
            
            # 缓存结果（如果没有错误）
            if "error" not in result:
                self._cache_result(cache_key, result)
            
            return result
            
        except git.InvalidGitRepositoryError:
            error_msg = f"{repo_path} 不是有效的Git仓库"
            logger.error(error_msg)
            return {"error": error_msg}
        except git.GitCommandError as e:
            error_msg = f"Git命令执行失败: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}
        except Exception as e:
            error_msg = f"审查Git差异时发生错误: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}
    
    def batch_review_files(self, file_paths: List[str]) -> Dict[str, Dict[str, Any]]:
        """批量审查多个文件"""
        logger.info(f"开始批量审查 {len(file_paths)} 个文件")
        
        results = {}
        failed_files = []
        
        # 使用线程池并发审查文件
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.config.concurrent_workers) as executor:
            # 提交所有任务
            future_to_file = {
                executor.submit(self._review_file_wrapper, file_path): file_path 
                for file_path in file_paths
            }
            
            # 处理完成的任务
            for future in concurrent.futures.as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    result = future.result()
                    results[file_path] = result
                except Exception as e:
                    logger.error(f"审查文件 {file_path} 时发生异常: {e}")
                    failed_files.append(file_path)
                    results[file_path] = {"error": str(e)}
        
        logger.info(f"批量审查完成，成功: {len(results) - len(failed_files)}, 失败: {len(failed_files)}")
        
        # 添加总体统计信息
        summary = {
            "total_files": len(file_paths),
            "successful_reviews": len(results) - len(failed_files),
            "failed_reviews": len(failed_files),
            "failed_files": failed_files,
            "timestamp": datetime.now().isoformat()
        }
        
        return {"summary": summary, "file_reviews": results}
    
    def _review_file_wrapper(self, file_path: str) -> Dict[str, Any]:
        """文件审查的包装函数，用于并发执行"""
        file_info = FileAnalyzer.analyze_file(file_path)
        if "error" in file_info:
            return file_info
        return self.review_file(file_path, file_info['content'])

class FileAnalyzer:
    @staticmethod
    def analyze_file(file_path: str) -> Dict[str, Any]:
        """分析文件并返回基本信息"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            lines = content.split('\n')
            line_count = len(lines)
            
            # 计算代码行、空行和注释行
            code_lines = 0
            comment_lines = 0
            blank_lines = 0
            
            # 判断文件语言
            file_ext = os.path.splitext(file_path)[1].lower()
            
            # 根据不同语言确定注释格式
            single_comment_markers = ['#', '//']
            multi_comment_start = '/*'
            multi_comment_end = '*/'
            in_multi_comment = False
            
            for line in lines:
                stripped_line = line.strip()
                
                if not stripped_line:
                    blank_lines += 1
                    continue
                
                # 检查是否在多行注释内
                if in_multi_comment:
                    comment_lines += 1
                    if multi_comment_end in stripped_line:
                        in_multi_comment = False
                    continue
                
                # 检查单行注释
                if any(stripped_line.startswith(marker) for marker in single_comment_markers):
                    comment_lines += 1
                    continue
                
                # 检查多行注释开始
                if multi_comment_start in stripped_line:
                    comment_lines += 1
                    if multi_comment_end not in stripped_line.split(multi_comment_start, 1)[1]:
                        in_multi_comment = True
                    continue
                
                # 否则视为代码行
                code_lines += 1
                
            # 计算文件大小
            file_size = os.path.getsize(file_path)
            
            # 估算token数量（粗略估算）
            estimated_tokens = len(content.split())
            
            return {
                "file_path": file_path,
                "file_name": os.path.basename(file_path),
                "file_size": file_size,
                "line_count": line_count,
                "code_lines": code_lines,
                "comment_lines": comment_lines,
                "blank_lines": blank_lines,
                "estimated_tokens": estimated_tokens,
                "content": content
            }
        except UnicodeDecodeError:
            return {"error": f"文件 {file_path} 不是有效的UTF-8编码文件"}
        except FileNotFoundError:
            return {"error": f"文件 {file_path} 不存在"}
        except Exception as e:
            return {"error": f"分析文件时发生错误: {str(e)}"}
    
    @staticmethod
    def find_files(directory: str, extensions: Optional[List[str]] = None) -> List[str]:
        """查找目录中的所有符合条件的文件"""
        result_files = []
        
        try:
            for root, _, files in os.walk(directory):
                for file in files:
                    # 跳过隐藏文件
                    if file.startswith('.'):
                        continue
                    
                    # 检查文件扩展名
                    if extensions:
                        file_ext = os.path.splitext(file)[1].lower()
                        if file_ext in extensions:
                            result_files.append(os.path.join(root, file))
                    else:
                        result_files.append(os.path.join(root, file))
            
            return result_files
        except Exception as e:
            logger.error(f"查找文件时发生错误: {e}")
            return []
    
    @staticmethod
    def filter_files_by_size(file_paths: List[str], min_size: int = 0, max_size: Optional[int] = None) -> List[str]:
        """根据文件大小过滤文件"""
        filtered = []
        
        for file_path in file_paths:
            try:
                size = os.path.getsize(file_path)
                if size >= min_size and (max_size is None or size <= max_size):
                    filtered.append(file_path)
            except Exception as e:
                logger.warning(f"无法获取文件大小 {file_path}: {e}")
        
        return filtered

def format_json_output(data: Any, indent: int = 2) -> str:
    """格式化JSON输出"""
    try:
        if isinstance(data, str):
            # 尝试解析字符串为JSON
            try:
                data = json.loads(data)
                return json.dumps(data, ensure_ascii=False, indent=indent)
            except json.JSONDecodeError:
                return data
        elif isinstance(data, (dict, list)):
            return json.dumps(data, ensure_ascii=False, indent=indent)
        else:
            return str(data)
    except Exception as e:
        logger.error(f"格式化输出时发生错误: {e}")
        return str(data)

def main():
    parser = argparse.ArgumentParser(description="代码审查智能体 - 基于AI的自动代码质量分析工具")
    
    # 基本参数组
    basic_group = parser.add_argument_group("基本参数")
    basic_group.add_argument('--file', type=str, help="要审查的单个文件路径")
    basic_group.add_argument('--dir', type=str, help="要批量审查的目录路径")
    basic_group.add_argument('--repo', type=str, help="Git仓库路径")
    basic_group.add_argument('--output', type=str, help="输出文件路径")
    basic_group.add_argument('--format', type=str, choices=['json', 'text'], default='json', help="输出格式")
    
    # 高级参数组
    advanced_group = parser.add_argument_group("高级参数")
    advanced_group.add_argument('--model', type=str, default="gpt-4o", help="使用的OpenAI模型")
    advanced_group.add_argument('--temperature', type=float, default=0.2, help="模型温度参数")
    advanced_group.add_argument('--max-tokens', type=int, default=4096, help="最大token数量")
    advanced_group.add_argument('--api-base', type=str, help="OpenAI API基础URL")
    
    # Git相关参数组
    git_group = parser.add_argument_group("Git相关参数")
    git_group.add_argument('--branch', type=str, default="main", help="比较的基准分支")
    git_group.add_argument('--commit-range', type=str, help="特定的提交范围 (如: commit1..commit2)")
    
    # 批处理参数组
    batch_group = parser.add_argument_group("批处理参数")
    batch_group.add_argument('--extensions', type=str, help="要包含的文件扩展名 (逗号分隔，如: .py,.js)")
    batch_group.add_argument('--min-size', type=int, default=0, help="最小文件大小 (字节)")
    batch_group.add_argument('--max-size', type=int, help="最大文件大小 (字节)")
    batch_group.add_argument('--workers', type=int, default=2, help="并发工作线程数")
    
    # 缓存参数组
    cache_group = parser.add_argument_group("缓存参数")
    cache_group.add_argument('--cache-dir', type=str, default=".cache", help="缓存目录路径")
    cache_group.add_argument('--no-cache', action='store_true', help="禁用结果缓存")
    
    args = parser.parse_args()
    
    # 验证参数
    input_args = [args.file, args.dir, args.repo]
    if sum(1 for arg in input_args if arg is not None) != 1:
        parser.error("必须提供且只能提供以下参数之一: --file, --dir, --repo")
    
    # 构建配置
    config_kwargs = {
        "model": args.model,
        "temperature": args.temperature,
        "max_tokens": args.max_tokens,
        "concurrent_workers": args.workers
    }
    
    if args.api_base:
        config_kwargs["api_base"] = args.api_base
    
    if args.no_cache:
        # 生成临时缓存目录以实际上禁用缓存
        import tempfile
        temp_cache = tempfile.mkdtemp()
        config_kwargs["cache_dir"] = temp_cache
    else:
        config_kwargs["cache_dir"] = args.cache_dir
    
    try:
        config = CodeReviewConfig(**config_kwargs)
        reviewer = CodeReviewer(config)
        
        # 执行审查
        if args.file:
            # 审查单个文件
            file_info = FileAnalyzer.analyze_file(args.file)
            if "error" in file_info:
                logger.error(f"文件分析错误: {file_info['error']}")
                sys.exit(1)
            
            logger.info(f"正在审查文件: {args.file}")
            logger.info(f"文件信息: {file_info['line_count']}行, {file_info['code_lines']}行代码, {file_info['file_size']}字节")
            
            result = reviewer.review_file(args.file, file_info['content'])
            
        elif args.dir:
            # 批量审查目录中的文件
            logger.info(f"正在扫描目录: {args.dir}")
            
            # 确定要包含的文件扩展名
            extensions = None
            if args.extensions:
                extensions = [ext.strip() for ext in args.extensions.split(',')]
                logger.info(f"只包含扩展名: {', '.join(extensions)}")
            
            # 查找文件
            file_paths = FileAnalyzer.find_files(args.dir, extensions)
            logger.info(f"找到 {len(file_paths)} 个文件")
            
            # 根据大小过滤文件
            if args.min_size > 0 or args.max_size:
                file_paths = FileAnalyzer.filter_files_by_size(
                    file_paths, 
                    min_size=args.min_size, 
                    max_size=args.max_size
                )
                size_filter_info = f"最小 {args.min_size} 字节"
                if args.max_size:
                    size_filter_info += f", 最大 {args.max_size} 字节"
                logger.info(f"应用大小过滤({size_filter_info})后，剩余 {len(file_paths)} 个文件")
            
            if not file_paths:
                logger.warning("没有找到符合条件的文件")
                sys.exit(0)
            
            # 执行批量审查
            result = reviewer.batch_review_files(file_paths)
            
        elif args.repo:
            # 审查Git仓库差异
            logger.info(f"正在审查Git仓库: {args.repo}")
            logger.info(f"基准分支: {args.branch}")
            if args.commit_range:
                logger.info(f"特定提交范围: {args.commit_range}")
            
            result = reviewer.review_git_diff(
                args.repo, 
                branch=args.branch, 
                commit_range=args.commit_range
            )
        
        # 格式化输出
        if args.format == 'text' and isinstance(result, (dict, list)):
            # 简单文本格式输出
            output_lines = []
            
            if 'summary' in result:
                output_lines.append("==== 审查摘要 ====")
                if isinstance(result['summary'], dict):
                    for key, value in result['summary'].items():
                        output_lines.append(f"{key}: {value}")
                else:
                    output_lines.append(str(result['summary']))
                output_lines.append("")
            
            if 'file_reviews' in result:
                output_lines.append("==== 文件审查结果 ====")
                for file_path, file_result in result['file_reviews'].items():
                    output_lines.append(f"\n文件: {file_path}")
                    if isinstance(file_result, dict):
                        if 'error' in file_result:
                            output_lines.append(f"  错误: {file_result['error']}")
                        elif 'code_quality' in file_result:
                            output_lines.append(f"  代码质量评分: {file_result['code_quality'].get('rating', 'N/A')}")
                            if 'potential_issues' in file_result:
                                output_lines.append(f"  潜在问题数: {len(file_result['potential_issues'])}")
            
            formatted_output = '\n'.join(output_lines)
        else:
            formatted_output = format_json_output(result)
        
        # 输出结果
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(formatted_output)
            logger.info(f"审查结果已保存到: {args.output}")
        else:
            print(formatted_output)
            
    except Exception as e:
        logger.error(f"程序执行错误: {e}")
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        # 清理临时缓存目录
        if args.no_cache and 'temp_cache' in locals():
            import shutil
            try:
                shutil.rmtree(temp_cache)
            except:
                pass

if __name__ == "__main__":
    main()