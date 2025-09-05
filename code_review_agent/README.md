# 代码审查智能体

一个基于大语言模型的自动化代码审查工具，可以帮助开发者分析代码质量、识别潜在问题并提供改进建议。

## 功能特点

- **单文件审查**：深入分析单个代码文件，提供详细的代码质量评估和改进建议
- **批量目录审查**：递归扫描并审查整个目录中的代码文件，支持并发处理
- **Git仓库差异审查**：对比Git仓库的分支差异或特定提交范围，分析代码变更的质量
- **多语言支持**：自动识别并适应不同编程语言的特点，提供针对性的审查建议
- **智能分析**：基于OpenAI的强大模型进行深度代码理解和分析
- **结构化输出**：以JSON或文本格式提供结构化的审查结果，便于集成到其他工具中
- **缓存机制**：自动缓存审查结果，提高重复审查的效率
- **文件过滤**：支持根据文件扩展名、大小等条件过滤要审查的文件
- **日志系统**：提供详细的操作日志，便于调试和问题追踪
- **API重试逻辑**：自动处理临时的API错误，提高系统的稳定性

## 安装要求

- Python 3.8+ 环境
- OpenAI API Key 或兼容的API服务

## 使用方法

1. 克隆或下载本项目到本地
2. 安装依赖：
```bash
pip install -r requirements.txt
```
3. 配置OpenAI API密钥：
   - 创建一个`.env`文件，内容参考`.env.example`
   - 或者直接在环境变量中设置`OPENAI_API_KEY`
4. 运行代码审查智能体：

### 审查单个文件

```bash
python code_review_agent.py --file example_code.py
```

### 批量审查目录

```bash
python code_review_agent.py --dir /path/to/code/directory --extensions .py,.js --workers 4
```

### 审查Git仓库差异

```bash
python code_review_agent.py --repo /path/to/your/git/repo --branch main
```

### 审查特定提交范围

```bash
python code_review_agent.py --repo /path/to/your/git/repo --commit-range abc123..def456
```

### 保存结果到文件

```bash
python code_review_agent.py --file example_code.py --output review_result.json
```

### 使用文本格式输出

```bash
python code_review_agent.py --file example_code.py --format text
```

## 参数说明

### 基本参数

| 参数 | 描述 | 是否必需 | 默认值 |
|------|------|----------|--------|
| `--file` | 要审查的单个文件路径 | 否 (与`--dir`/`--repo`三选一) | 无 |
| `--dir` | 要批量审查的目录路径 | 否 (与`--file`/`--repo`三选一) | 无 |
| `--repo` | Git仓库路径 | 否 (与`--file`/`--dir`三选一) | 无 |
| `--output` | 输出文件路径 | 否 | 控制台输出 |
| `--format` | 输出格式 (json/text) | 否 | json |

### 高级参数

| 参数 | 描述 | 是否必需 | 默认值 |
|------|------|----------|--------|
| `--model` | 使用的OpenAI模型 | 否 | gpt-4o |
| `--temperature` | 模型温度参数 | 否 | 0.2 |
| `--max-tokens` | 最大token数量 | 否 | 4096 |
| `--api-base` | OpenAI API基础URL | 否 | 官方API URL |

### Git相关参数

| 参数 | 描述 | 是否必需 | 默认值 |
|------|------|----------|--------|
| `--branch` | 比较的基准分支 | 否 | main |
| `--commit-range` | 特定的提交范围 (如: commit1..commit2) | 否 | 无 |

### 批处理参数

| 参数 | 描述 | 是否必需 | 默认值 |
|------|------|----------|--------|
| `--extensions` | 要包含的文件扩展名 (逗号分隔，如: .py,.js) | 否 | 所有文件 |
| `--min-size` | 最小文件大小 (字节) | 否 | 0 |
| `--max-size` | 最大文件大小 (字节) | 否 | 无限制 |
| `--workers` | 并发工作线程数 | 否 | 2 |

### 缓存参数

| 参数 | 描述 | 是否必需 | 默认值 |
|------|------|----------|--------|
| `--cache-dir` | 缓存目录路径 | 否 | .cache |
| `--no-cache` | 禁用结果缓存 | 否 | 启用缓存 |

## 返回结果格式

### JSON格式

审查结果以JSON格式返回，包含以下主要字段：

```json
{
  "summary": {
    "total_files": 1,
    "reviewed_files": 1,
    "issues_found": 3,
    "average_rating": 7.5
  },
  "file_reviews": {
    "example_code.py": {
      "file_path": "example_code.py",
      "file_info": {
        "line_count": 50,
        "code_lines": 35,
        "comment_lines": 5,
        "blank_lines": 10,
        "file_size": 1200
      },
      "code_quality": {
        "rating": 7.5,
        "summary": "整体代码质量良好，但存在一些潜在问题需要修复"
      },
      "potential_issues": [
        {
          "severity": "high",
          "description": "除法操作未处理除数为零的情况",
          "suggestion": "添加条件检查以避免除零错误",
          "line_numbers": [15]
        },
        {
          "severity": "medium",
          "description": "函数缺少文档字符串",
          "suggestion": "添加详细的文档字符串描述函数功能、参数和返回值",
          "line_numbers": [25]
        }
      ],
      "improvement_suggestions": [
        "考虑使用类型注解提高代码可读性",
        "重构重复代码片段为可重用函数"
      ],
      "best_practices": [
        "变量命名清晰易懂",
        "代码结构合理，易于理解"
      ],
      "language_specific_analysis": "Python特定的优化建议和注意事项"
    }
  }
}
```

### 文本格式

当使用`--format text`参数时，输出会以更易读的文本格式展示，包含主要的审查信息和摘要。

## 技术实现细节

### 核心组件

1. **CodeReviewConfig**：配置类，负责管理API密钥、模型参数、缓存设置等配置信息
2. **CodeReviewer**：核心审查类，实现代码审查的主要逻辑
3. **FileAnalyzer**：文件分析类，提供文件元数据提取、代码统计等功能

### 运行流程

1. **参数解析**：解析命令行参数，验证输入有效性
2. **配置初始化**：根据参数初始化审查配置
3. **文件处理**：对于目录审查，扫描并过滤符合条件的文件
4. **代码审查**：调用OpenAI API进行代码分析，处理重试和错误
5. **结果处理**：格式化审查结果，支持JSON和文本输出
6. **缓存管理**：自动缓存和读取审查结果，提高效率

### 关键技术

1. **大语言模型集成**：使用OpenAI API进行深度代码理解和分析
2. **并发处理**：使用线程池实现批量文件的并行审查
3. **缓存机制**：基于文件哈希和时间戳的智能缓存策略
4. **Git集成**：使用GitPython和PyGitHub库实现Git仓库分析
5. **结构化输出**：统一的JSON格式输出，便于集成和处理

## 注意事项

1. 请确保您的OpenAI API密钥有足够的额度和权限
2. 对于大文件或复杂仓库，可能会消耗较多的API调用次数和token
3. 建议在本地开发环境中使用，暂不推荐直接用于生产环境的代码质量保障
4. 审查结果仅供参考，最终代码质量判断请以开发者的专业知识为准
5. 对于特别大的目录或仓库审查，建议调整`--workers`参数以控制并发数量

## 示例

项目包含一个`example_code.py`文件，用于演示代码审查功能。您可以运行以下命令查看示例：

```bash
python code_review_agent.py --file example_code.py
```

## 批量审查示例

审查当前目录下所有Python文件，排除小于100字节和大于10000字节的文件：

```bash
python code_review_agent.py --dir . --extensions .py --min-size 100 --max-size 10000 --workers 4
```

## 性能优化建议

1. 对于频繁审查的代码库，启用缓存可以显著提高性能
2. 对于大型项目，使用`--extensions`和`--max-size`参数过滤文件可以减少API调用
3. 调整`--workers`参数以平衡性能和资源占用，通常2-4个线程较为合适
4. 对于不重要的审查任务，可以考虑使用成本更低的模型如`gpt-3.5-turbo`

## 许可证

MIT License