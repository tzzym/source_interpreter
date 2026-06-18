# source-interpreter

一款Agent工具，用于对代码项目的功能进行分析。本项目采用DFS算法，对每个目录、代码文件、代码内容进行作用分析。具体方法见 `workflow\README.md` 。

## 项目结构

```
source_interpreter
      │
      ├──  __init__.py  python项目固定格式
      │
      ├──  __main__.py  主入口。
      │
      ├──  ai_client.py  连接AI服务器
      │
      └──  workflow  文件夹，用于递归分析
```

### __main__.py

因为source_interpreter既支持基于文件夹的分析，也支持仅分析单个文件，所以需要这个程序进行分类处理。

## 使用方法

本项目 `__main__.py` 还没有完成。只能使用AI调用 `workflow` 里的函数来实现功能
