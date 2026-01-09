from datetime import datetime
from agent.config import VERSION


def calculate_time_diff(start_date, end_date):
    # 计算年份差
    years = end_date.year - start_date.year
    months = end_date.month - start_date.month
    days = end_date.day - start_date.day
    hours = end_date.hour - start_date.hour
    minutes = end_date.minute - start_date.minute

    # 处理借位
    if minutes < 0:
        minutes += 60
        hours -= 1

    if hours < 0:
        hours += 24
        days -= 1

    if days < 0:
        # 获取上个月的天数
        if end_date.month == 1: # 特殊年份-易错
            last_month = 12
            last_year = end_date.year - 1
        else:
            last_month = end_date.month - 1
            last_year = end_date.year

        # 计算上个月的天数
        if last_month in [4, 6, 9, 11]:
            days_in_last_month = 30
        elif last_month == 2:
            # 检查闰年
            if (last_year % 400 == 0) or (last_year % 100 != 0 and last_year % 4 == 0):
                days_in_last_month = 29
            else:
                days_in_last_month = 28
        else:
            days_in_last_month = 31
        # 借位计算
        days += days_in_last_month
        months -= 1

    if months < 0:
        months += 12
        years -= 1

    return years, months, days, hours, minutes


date_time = datetime.now()
comparison_date = datetime(2026, 1, 1, 10, 23)

# 计算时间差
years, months, days, hours, minutes = calculate_time_diff(comparison_date, date_time)

# 按照格式输出
time_parts = []
if years > 0:
    time_parts.append(str(years))
if months > 0:
    time_parts.append(str(months))
if days > 0:
    time_parts.append(str(days))
if hours > 0:
    time_parts.append(str(hours))

# 输出格式化的时间差
if time_parts:
    print(f"距离{VERSION}版本发布已经过去了{'-'.join(time_parts)}")
