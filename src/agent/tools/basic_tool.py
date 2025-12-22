import math
import re
import datetime
import statistics
from datetime import datetime as dt
from typing import Optional, Dict, Any, List
from langchain_core.tools import tool
from datetime import datetime, timedelta




def get_datetime():
    current_date = datetime.date.today()
    year = current_date.year  # 2025
    month = current_date.month  # 11
    day = current_date.day  # 30
    return f"{year}年{month}月{day}日"

@tool('get_date')
def get_date()->str:
    """获取当前时间的日期
    Returns:
        str: 返回当前的日期信息(中文描述)
    Example:
        "get_date.run("") 返回2025年11月30日"
    """
    return get_datetime()

@tool("get_time")
def get_time() -> str:
    """获取当前时间
    Returns:
        str: 当前时间（24小时制）
    Example:
        例如:get_time.run() → "14:30"
    """
    now = dt.now()
    current_time = now.strftime("%H:%M")
    return current_time

@tool("date_calculate")
def date_calculate(base_date: Optional[str] = None, days_diff: int = 0) -> str: # 日期计算函数-base_date可以为none或者str
    """对日期进行加减计算（默认基于当前日期）
    Args:
        base_date: 基准日期（可选，格式如「2025-12-01」，不传入则是默认当前日期）
        days_diff: 加减天数（正数加，负数减，如 3=3天后，-1=昨天）
    Returns:
        str: 计算后的日期（中文格式）
    Example:
        date_calculate.run("2025-12-01", 3) → "2025年12月4日"
        date_calculate.run(days=-1) → "2025年11月30日"
    """
    if base_date is not None:
        base = datetime.datetime.strptime(base_date, "%Y-%m-%d")
    else:
        base = datetime.datetime.now() # 默认日期
    target = base + datetime.timedelta(days=days_diff) # 计算真实的日期
    return target.strftime("%Y年%m月%d日")





@tool("time_calculate")
def time_calculate(base_time: Optional[str] = None, hours_diff: int = 0, minutes_diff: int = 0) -> str:
    """对时间进行加减计算（默认基于当前时间）
    Args:
        base_time: 基准时间（可选，格式如「14:30」，不传入则是默认当前时间）
        hours_diff: 加减小时数（正数加，负数减，如 3=3小时后，-1=1小时前）
        minutes_diff: 加减分钟数（正数加，负数减，如 30=30分钟后，-15=15分钟前）
    Returns:
        str: 计算后的时间（中文格式）
    Example:
        time_calculate.run("14:30", hours=2, minutes=30) → "下午3:00"
    """
    # 处理基准时间
    if base_time is not None:
        # 解析输入的时间字符串
        base = datetime.strptime(base_time, "%H:%M")
    else:
        # 使用当前时间
        base = datetime.now()

    # 计算目标时间
    target = base + timedelta(hours=hours_diff, minutes=minutes_diff)

    # 格式化输出
    hour = target.hour
    minute = target.minute

    # 判断时段
    if 0 <= hour < 6:
        period = "凌晨"
    elif 6 <= hour < 12:
        period = "上午"
    elif 12 <= hour < 18:
        period = "下午"
    else:
        period = "晚上"

    # 转换为12小时制
    display_hour = hour if hour <= 12 else hour - 12
    if display_hour == 0:
        display_hour = 12

    # 格式化分钟
    minute_str = f"{minute:02d}"

    return f"{period}{display_hour}:{minute_str}"

@tool('calculator',parse_docstring= True)
def calculator(expression:str)->str:
    """计算数学表达式，支持基本运算和常用数学函数，主要支持的是python语言的数值计算。

    Args:
        expression (str): 要计算的数学表达式，支持以下运算：
            - 基本运算：+, -, *, /, ^, %
            - 括号：()
            - 数学函数：sqrt(x), sin(x), cos(x), tan(x), log(x), exp(x), abs(x)
            - 常量：pi, e
            - 支持角度符号：如 sin(30°)

    Returns:
        str: 计算结果的字符串形式，如果出错则返回错误信息
    """
    safe_dict = {
        '__builtins__': None, # 禁用
        'math': math,
        'sqrt': math.sqrt,
        'sin': math.sin,
        'cos': math.cos,
        'tan': math.tan,
        'log': math.log,
        'exp': math.exp,
        'pi': math.pi,
        'e': math.e,
        'abs': abs,
        'min': min,
        'max': max,
    }
    try:
        # 计算表达式
        processed_expr = expression.strip() # strip() 方法用于移除字符串两端的空白字符（包括空格、制表符、换行符等）。
        # 替换^为**（支持幂运算）
        processed_expr = processed_expr.replace('^', '**') # 字符串的替换函数
        # 替换角度符号°：将 "sin(30°)" 转为 "sin(radians(30))"
        # 正则匹配：数字+°（支持整数、小数，如30°、45.5°）
        processed_expr = re.sub(
            r'(\d+(?:\.\d+)?)°',  # 匹配带小数的数字+°
            lambda m: f'radians({m.group(1)})',  # 替换为radians(数字)
            processed_expr
        )
        result = eval(expression, safe_dict) # 限制可访问的函数变量
        if isinstance(result,float):
            result = f"{result:.8f}".strip("0").rstrip(".")
            return result
        return str(result)
    except SyntaxError:
        return "计算错误：表达式语法错误（比如括号不匹配、运算符使用不当）"
    except ValueError as e:
        return f"计算错误：数值超出定义域（比如log(-1)、sqrt(-2)）：{str(e)}"
    except TypeError as e:
        return f"计算错误：参数类型错误（比如给三角函数传了字符串）：{str(e)}"
    except ZeroDivisionError:
        return "计算错误：除数不能为0"
    except Exception as e:
        return f"计算错误：{str(e)}"
@tool("validate_email")
def validate_email(email: str) -> str:
    """验证输入字符串是否为合法邮箱格式
    Args:
        email: 待验证邮箱（如 "user@example.com"）
    Returns:
        str: 验证结果（成功/失败原因）
    Example:
        validate_email.run("user@example.com") → "合法邮箱格式"
        validate_email.run("user.example.com") → "非法邮箱：缺少@符号"
    """
    email_pattern = re.compile(r"^[a-zA-Z0-9_-]+@[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+$")
    if not email:
        return "非法邮箱：输入为空"
    if email_pattern.match(email):
        return "合法邮箱格式"
    elif "@" not in email:
        return "非法邮箱：缺少@符号"
    elif "." not in email.split("@")[-1]:
        return "非法邮箱：缺少顶级域名（如 .com）"
    else:
        return "非法邮箱：格式不符合规范"

@tool
def echo(text: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """调试/回显"""
    return {"text": text, "metadata": metadata or {}}

@tool
def stats(values: List[float]) -> Dict[str, float]:
    """简单统计"""
    if not values:
        raise ValueError("values is empty")
    return {
        "count": float(len(values)),
        "min": float(min(values)),
        "max": float(max(values)),
        "mean": float(statistics.mean(values)),
        "median": float(statistics.median(values)),
        "stdev": float(statistics.pstdev(values)),
    }



if __name__ == "__main__":
    print(calculator.description)
    result2 = calculator.run("2+3**4+exp(8)") # 非普通函数必须用Run来运行
    print(result2)

