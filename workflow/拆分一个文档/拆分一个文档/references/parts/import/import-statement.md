7.11. import 语句
----------------

```
import_stmt:     "import"  ["as" identifier] (","  ["as" identifier])*
                 | "from"  "import" identifier ["as" identifier]
                 ("," identifier ["as" identifier])*
                 | "from"  "import" "(" identifier ["as" identifier]
                 ("," identifier ["as" identifier])* [","] ")"
                 | "from"  "import" "*"
module:          (identifier ".")* identifier
relative_module: "."*  | "."+
```

基本的 import 语句（不带 `from` 子句）会分两步执行:

1.  查找一个模块，如果有必要还会加载并初始化模块。
2.  在当前作用域的命名空间中定义与 `import` 语句同位置的名称，就像赋值语句那样（包括 `global` 和 `nonlocal` 的语义）。

当语句包含多个子句（由逗号分隔）时这两个步骤将对每个子句分别执行，如同这些子句被分成独立的 import 语句一样。

第一个步骤，即查找和加载模块的细节在 [导入系统](import.html#importsystem) 一节中有更详细的描述，其中也描述了可被导入的多种类型的包和模块，以及可用于定制导入系统的所有钩子对象。 请注意如果这一步失败，则可能说明模块无法找到， _或者_ 是在初始化模块，包括执行模块代码期间发生了错误。

如果成功获取到请求的模块，则可以通过以下三种方式之一在局部命名空间中使用它:

*   模块名后使用 `as` 时，直接把 `as` 后的名称与导入模块绑定。
*   如果没有指定其他名称，且被导入的模块为最高层级模块，则模块的名称将被绑定到局部命名空间作为对所导入模块的引用。
*   如果被导入的模块 _不是_ 最高层级模块，则包含该模块的最高层级包的名称将被绑定到局部命名空间作为对该最高层级包的引用。 所导入的模块必须使用其完整限定名称来访问而不能直接访问。

`from` 形式使用的过程略微繁复一些:

1.  查找 `from` 子句中指定的模块，如有必要还会加载并初始化模块；
2.  对于 `import` 子句中指定的每个标识符：
    1.  检查被导入模块是否有该名称的属性
    2.  如果没有，尝试导入具有该名称的子模块，然后再次检查被导入模块是否有该属性
    3.  如果未找到该属性，则引发 [`ImportError`](../library/exceptions.html#ImportError "ImportError") 。
    4.  如果找到，则将该值的引用存储到当前命名空间中，如果存在 `as` 子句则使用其中的名称，否则使用属性名。

示例:

```python
import foo                 # foo 被导入并且被局部绑定
import foo.bar.baz         # foo, foo.bar 和 foo.bar.baz 被导入，foo 被局部绑定
import foo.bar.baz as fbb  # foo, foo.bar 和 foo.bar.baz 被导入，foo.bar.baz 被绑定为 fbb
from foo.bar import baz    # foo, foo.bar 和 foo.bar.baz 被导入，foo.bar.baz 被绑定为 baz
from foo import attr       # foo 被导入并且 foo.attr 被绑定为 attr
```

如果标识符列表改为一个星号 (`'*'`)，则在模块中定义的全部公有名称都将按 `import` 语句所在的作用域被绑定到局部命名空间。

一个模块所定义的 _公有名称_ 是由在模块命名空间中检查名为 `__all__` 的变量来确定的；如果有定义，它必须是一个字符串列表，其中的项为该模块所定义或导入的名称。 包含非 ASCII 字符的名称必须是 [normalization form](https://www.unicode.org/reports/tr15/#Norm_Forms) NFKC；详情参见 [名称中的非 ASCII 字符](lexical_analysis.html#lexical-names-nonascii) 。 在 `__all__` 中给出的名称都会被视为公有并且必须存在。 如果未定义 `__all__` ，则公有名称的集合将包括在模块的命名空间中找到的所有不以下划线字符 (`'_'`) 打头的名称。 `__all__` 应当包含整个公有 API。 它的目标是避免意外地导出不属于 API 的组成部分的项（例如在模块内部被导入和使用的库模块）。

通配符形式的导入 --- `from module import *` --- 仅在模块层级上被允许。 尝试在类或函数定义中使用它将引发 [`SyntaxError`](../library/exceptions.html#SyntaxError "SyntaxError") 。

当指定要导入哪个模块时，你不必指定模块的绝对名称。 当一个模块或包被包含在另一个包之中时，可以在同一个最高层级包中进行相对导入，而不必提及包名称。 通过在 `from` 之后指定的模块或包中使用前缀点号，你可以在不指定确切名称的情况下指明在当前包层级结构中要上溯多少级。 一个前缀点号表示是执行导入的模块所在的当前包，两个点号表示上溯一个包层级。 三个点号表示上溯两级，依此类推。 因此如果你执行 `from . import mod` 时所处位置为 `pkg` 包内的一个模块，则最终你将导入 `pkg.mod` 。 如果你执行 `from ..subpkg2 import mod` 时所处位置为 `pkg.subpkg1` 则你将导入 `pkg.subpkg2.mod` 。 有关相对导入的规范说明包含在 [包相对导入](import.html#relativeimports) 一节中。

[`importlib.import_module()`](../library/importlib.html#importlib.import_module "importlib.import_module") 被提供用来为动态地确定要导入模块的应用提供支持。

引发一个 [审计事件](../library/sys.html#auditing) `import` 并附带参数 `module`, `filename`, `sys.path`, `sys.meta_path`, `sys.path_hooks` 。

### 7.11.1. future 语句

_future 语句_ 是一种针对编译器的指令，指明某个特定模块应当使用在特定的未来某个 Python 发行版中成为标准特性的语法或语义。

future 语句的目的是使得向在语言中引入了不兼容改变的 Python 未来版本的迁移更为容易。 它允许基于每个模块在某种新特性成为标准之前的发行版中使用该特性。

```
future_stmt: "from" "__future__" "import"  ["as" identifier]
             (","  ["as" identifier])*
             | "from" "__future__" "import" "("  ["as" identifier]
             (","  ["as" identifier])* [","] ")"
feature:     identifier
```

future 语句必须在靠近模块开头的位置出现。 可以出现在 future 语句之前的行只有:

*   模块的文档字符串（如果存在），
*   注释，
*   空行，以及
*   其他 future 语句。

唯一需要使用 future 语句的特性是 `annotations` (参见 [**PEP 563**](https://peps.python.org/pep-0563/))。

future 语句所启用的所有历史特性仍然为 Python 3 所认可。 其中包括 `absolute_import`, `division`, `generators`, `generator_stop`, `unicode_literals`, `print_function`, `nested_scopes` 和 `with_statement` 。 它们都已成为冗余项，因为它们总是为已启用状态，保留它们只是为了向后兼容。

future 语句在编译时会被识别并做特殊对待：对核心构造语义的改变常常是通过生成不同的代码来实现。 新的特性甚至可能会引入新的不兼容语法（例如新的保留字），在这种情况下编译器可能需要以不同的方式来解析模块。 这样的决定不能推迟到运行时方才作出。

对于任何给定的发布版本，编译器要知道哪些特性名称已被定义，如果某个 future 语句包含未知的特性则会引发编译时错误。

直接运行时的语义与任何 import 语句相同：存在一个后文将详细说明的标准模块 [`__future__`](../library/__future__.html#module-__future__ "__future__: Future statement definitions") ，它会在执行 future 语句时以通常的方式被导入。

相应的运行时语义取决于 future 语句所启用的指定特性。

请注意以下语句没有任何特别之处:

```python
import __future__ [as name]
```

这并非 future 语句；它只是一条没有特殊语义或语法限制的普通 import 语句。

在默认情况下，通过对内置函数 [`exec()`](../library/functions.html#exec "exec") 和 [`compile()`](../library/functions.html#compile "compile") 的调用编译的代码如果出现于一个包含有 future 语句的模块 `M` 之中，就会使用该 future 语句所关联的语法和语义。 此行为可以通过传给 `compile()` 的可选参数来控制 --- 请参阅该函数的文档了解详情。

在交互式解释器提示符中键入的 future 语句将在解释器会话此后的交互中有效。 如果一个解释器的启动使用了 [`-i`](../using/cmdline.html#cmdoption-i) 选项启动，并传入了一个脚本名称来执行，且该脚本包含 future 语句，它将在交互式会话开始执行脚本之后保持有效。

参见

[**PEP 236**](https://peps.python.org/pep-0236/) - 回到 \_\_future\_\_

有关 \_\_future\_\_ 机制的最初提议。