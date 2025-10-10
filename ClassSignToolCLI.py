import requests
import json
import time
import datetime
import sys
import os

student_id = ''  # 请填写你的学号


# 颜色代码
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'


def clear_screen():
    """清屏"""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_header(title):
    """打印标题"""
    clear_screen()
    print(f"{Colors.CYAN}{'=' * 60}{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}{title:^60}{Colors.END}")
    print(f"{Colors.CYAN}{'=' * 60}{Colors.END}")
    print()


def print_menu(options):
    """打印菜单"""
    for i, option in enumerate(options, 1):
        print(f"  {Colors.YELLOW}{i}.{Colors.END} {option}")
    print()


def get_choice(prompt, min_val, max_val):
    """获取用户选择"""
    while True:
        try:
            choice = input(f"{Colors.GREEN}{prompt}: {Colors.END}")
            if choice.lower() == 'q':
                return 'q'
            choice = int(choice)
            if min_val <= choice <= max_val:
                return choice
            else:
                print(f"{Colors.RED}请输入 {min_val}-{max_val} 之间的数字{Colors.END}")
        except ValueError:
            print(f"{Colors.RED}请输入有效的数字{Colors.END}")


def get_date_input(prompt):
    """获取用户输入的日期"""
    while True:
        date_str = input(f"{Colors.GREEN}{prompt} (格式: YYYYMMDD, 例如: 20250924): {Colors.END}")
        if date_str.lower() == 'q':
            return 'q'
        try:
            datetime.datetime.strptime(date_str, '%Y%m%d')
            return date_str
        except ValueError:
            print(f"{Colors.RED}日期格式错误，请重新输入{Colors.END}")


def login():
    """登录并获取用户ID和sessionId"""
    print_header("登录系统")
    print(f"{Colors.YELLOW}正在登录...{Colors.END}")

    url = 'https://iclass.buaa.edu.cn:8346/app/user/login.action'
    para = {
        'phone': input(f"{Colors.BLUE}请输入学号: {Colors.END}"),
        'userLevel': '1',
        'verificationType': '2',
        'verificationUrl': ''
    }

    try:
        res = requests.get(url=url, params=para, timeout=10)
        print(f"{Colors.BLUE}登录响应状态码: {res.status_code}{Colors.END}")

        # 尝试解析JSON
        userData = json.loads(res.text)

        if userData.get('STATUS') != '0':
            print(f"{Colors.RED}登录失败: {userData.get('ERRORMSG', '未知错误')}{Colors.END}")
            input(f"{Colors.YELLOW}按回车键继续...{Colors.END}")
            return None, None

        userId = userData['result']['id']
        sessionId = userData['result']['sessionId']
        print(f"{Colors.GREEN}✓ 登录成功: userId={userId}, sessionId={sessionId}{Colors.END}")
        time.sleep(1)
        return userId, sessionId

    except json.JSONDecodeError as e:
        print(f"{Colors.RED}JSON解析错误: {e}{Colors.END}")
        print(f"{Colors.RED}响应内容不是有效的JSON格式{Colors.END}")
        input(f"{Colors.YELLOW}按回车键继续...{Colors.END}")
        return None, None
    except requests.RequestException as e:
        print(f"{Colors.RED}网络请求错误: {e}{Colors.END}")
        input(f"{Colors.YELLOW}按回车键继续...{Colors.END}")
        return None, None
    except KeyError as e:
        print(f"{Colors.RED}响应数据缺少必要字段: {e}{Colors.END}")
        input(f"{Colors.YELLOW}按回车键继续...{Colors.END}")
        return None, None


def get_course_schedule(userId, sessionId, dateStr):
    """获取指定日期的课程表"""
    url = 'https://iclass.buaa.edu.cn:8346/app/course/get_stu_course_sched.action'
    para = {
        'dateStr': dateStr,
        'id': userId
    }
    headers = {
        'sessionId': sessionId,
    }

    try:
        res = requests.get(url=url, params=para, headers=headers, timeout=10)
        return json.loads(res.text)
    except Exception as e:
        print(f"{Colors.RED}获取课程表失败: {e}{Colors.END}")
        return None


def sign_course(userId, courseSchedId):
    """课程打卡"""
    params = {
        'id': userId
    }
    current_timestamp_milliseconds = int(time.time() * 1000)
    url = f'http://iclass.buaa.edu.cn:8081/app/course/stu_scan_sign.action?courseSchedId={courseSchedId}&timestamp={current_timestamp_milliseconds}'

    try:
        r = requests.post(url=url, params=params, timeout=10)
        return r.ok
    except Exception as e:
        print(f"{Colors.RED}打卡请求失败: {e}{Colors.END}")
        return False


def process_single_day(userId, sessionId, date_str):
    """处理单个日期的打卡"""
    print_header(f"处理日期: {date_str}")

    json_data = get_course_schedule(userId, sessionId, date_str)
    if json_data is None:
        print(f"{Colors.RED}获取课程表失败{Colors.END}")
        input(f"{Colors.YELLOW}按回车键返回...{Colors.END}")
        return

    if json_data['STATUS'] == '0' and 'result' in json_data:
        courses = json_data['result']
        if not courses:
            print(f"{Colors.YELLOW}{date_str} 没有课程{Colors.END}")
            input(f"{Colors.YELLOW}按回车键返回...{Colors.END}")
            return

        print(f"{Colors.GREEN}{date_str} 有 {len(courses)} 门课程:{Colors.END}")
        print()

        for i, item in enumerate(courses, 1):
            courseSchedId = item['id']
            courseName = item['courseName']
            classBeginTime = item['classBeginTime']
            classEndTime = item['classEndTime']

            date_display = classBeginTime[:10]
            begin = classBeginTime[11:16]
            end = classEndTime[11:16]

            print(f"{Colors.CYAN}{i}. {courseName}{Colors.END}")
            print(f"   时间: {begin}-{end}")
            print(f"   日期: {date_display}")
            print()

        print(f"{Colors.YELLOW}请选择要打卡的课程:{Colors.END}")
        print(f"  {Colors.GREEN}a{Colors.END} - 打卡所有课程")
        print(f"  {Colors.YELLOW}1-{len(courses)}{Colors.END} - 打卡指定课程")
        print(f"  {Colors.RED}q{Colors.END} - 返回主菜单")
        print()

        choice = input(f"{Colors.GREEN}请输入选择: {Colors.END}").lower()

        if choice == 'q':
            return
        elif choice == 'a':
            # 打卡所有课程
            for i, item in enumerate(courses, 1):
                courseSchedId = item['id']
                courseName = item['courseName']
                classBeginTime = item['classBeginTime']
                classEndTime = item['classEndTime']

                date_display = classBeginTime[:10]
                begin = classBeginTime[11:16]
                end = classEndTime[11:16]

                print(f"{Colors.BLUE}正在打卡: {courseName}...{Colors.END}")
                if sign_course(userId, courseSchedId):
                    print(f"{Colors.GREEN}✓ 已打卡: {date_display}\t{courseName}\t{begin}-{end}{Colors.END}")
                else:
                    print(f"{Colors.RED}✗ 打卡失败: {date_display}\t{courseName}\t{begin}-{end}{Colors.END}")
                time.sleep(1)  # 稍微延迟一下，避免请求过快
        elif choice.isdigit() and 1 <= int(choice) <= len(courses):
            # 打卡指定课程
            idx = int(choice) - 1
            item = courses[idx]
            courseSchedId = item['id']
            courseName = item['courseName']
            classBeginTime = item['classBeginTime']
            classEndTime = item['classEndTime']

            date_display = classBeginTime[:10]
            begin = classBeginTime[11:16]
            end = classEndTime[11:16]

            print(f"{Colors.BLUE}正在打卡: {courseName}...{Colors.END}")
            if sign_course(userId, courseSchedId):
                print(f"{Colors.GREEN}✓ 已打卡: {date_display}\t{courseName}\t{begin}-{end}{Colors.END}")
            else:
                print(f"{Colors.RED}✗ 打卡失败: {date_display}\t{courseName}\t{begin}-{end}{Colors.END}")
        else:
            print(f"{Colors.RED}无效选择{Colors.END}")

        input(f"{Colors.YELLOW}按回车键继续...{Colors.END}")
    else:
        print(f"{Colors.RED}获取课程表失败: {json_data.get('ERRORMSG', '未知错误')}{Colors.END}")
        input(f"{Colors.YELLOW}按回车键返回...{Colors.END}")


def process_date_range(userId, sessionId, start_date_str, end_date_str):
    """处理日期范围内的打卡"""
    start_date = datetime.datetime.strptime(start_date_str, '%Y%m%d')
    end_date = datetime.datetime.strptime(end_date_str, '%Y%m%d')

    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime('%Y%m%d')
        process_single_day(userId, sessionId, date_str)

        # 询问是否继续下一天
        if current_date < end_date:
            print(f"{Colors.YELLOW}是否继续处理下一天 ({date_str})?{Colors.END}")
            print(f"  {Colors.GREEN}y{Colors.END} - 继续")
            print(f"  {Colors.RED}n{Colors.END} - 返回主菜单")
            print()
            answer = input(f"{Colors.GREEN}请输入选择: {Colors.END}").lower()
            if answer != 'y':
                break

        current_date += datetime.timedelta(days=1)


def process_continuous_days(userId, sessionId, start_date_str):
    """从指定日期开始连续打卡，直到连续7天没课"""
    cnt = 0  # 连续没课的天数
    current_date = datetime.datetime.strptime(start_date_str, '%Y%m%d')

    for i in range(120):  # 最多检查120天
        if cnt == 7:
            print(f"{Colors.YELLOW}连续7天没课，可能是假期，程序退出{Colors.END}")
            input(f"{Colors.YELLOW}按回车键继续...{Colors.END}")
            break

        date_str = current_date.strftime('%Y%m%d')
        print_header(f"检查日期: {date_str}")

        # 查询课表
        json_data = get_course_schedule(userId, sessionId, date_str)
        if json_data is None:
            current_date += datetime.timedelta(days=1)
            continue

        if json_data['STATUS'] == '0' and 'result' in json_data:
            courses = json_data['result']
            if not courses:
                print(f"{Colors.YELLOW}{date_str} 没有课程{Colors.END}")
                cnt += 1
                current_date += datetime.timedelta(days=1)

                # 每检查5天提示一次进度
                if cnt % 5 == 0:
                    print(f"{Colors.BLUE}已连续 {cnt} 天没有课程{Colors.END}")
                    input(f"{Colors.YELLOW}按回车键继续...{Colors.END}")
                continue

            cnt = 0  # 重置连续没课计数
            print(f"{Colors.GREEN}{date_str} 有 {len(courses)} 门课程:{Colors.END}")
            print()

            for item in courses:
                courseSchedId = item['id']
                courseName = item['courseName']
                classBeginTime = item['classBeginTime']
                classEndTime = item['classEndTime']

                date_display = classBeginTime[:10]
                begin = classBeginTime[11:16]
                end = classEndTime[11:16]

                print(f"{Colors.CYAN}课程: {courseName}{Colors.END}")
                print(f"时间: {begin}-{end}")

                # 执行打卡
                print(f"{Colors.BLUE}正在打卡...{Colors.END}")
                if sign_course(userId, courseSchedId):
                    print(f"{Colors.GREEN}✓ 已打卡: {date_display}\t{courseName}\t{begin}-{end}{Colors.END}")
                else:
                    print(f"{Colors.RED}✗ 打卡失败: {date_display}\t{courseName}\t{begin}-{end}{Colors.END}")

                time.sleep(1)  # 稍微延迟一下，避免请求过快

            print()
            print(f"{Colors.YELLOW}是否继续处理下一天?{Colors.END}")
            print(f"  {Colors.GREEN}y{Colors.END} - 继续")
            print(f"  {Colors.RED}n{Colors.END} - 返回主菜单")
            print()
            answer = input(f"{Colors.GREEN}请输入选择: {Colors.END}").lower()
            if answer != 'y':
                print(f"{Colors.YELLOW}用户选择退出{Colors.END}")
                return

            current_date += datetime.timedelta(days=1)
        else:
            print(f"{Colors.RED}获取课程表失败: {json_data.get('ERRORMSG', '未知错误')}{Colors.END}")
            cnt += 1
            current_date += datetime.timedelta(days=1)


def main():
    # 首先登录
    userId, sessionId = login()
    if not userId or not sessionId:
        return

    while True:
        print_header("课程打卡系统")
        print(f"{Colors.BLUE}欢迎使用课程打卡系统!{Colors.END}")
        print()

        menu_options = [
            "指定单个日期打卡",
            "指定日期范围打卡",
            "从指定日期开始连续打卡",
            "退出系统"
        ]

        print_menu(menu_options)

        choice = get_choice("请选择操作", 1, 4)

        if choice == 'q':
            break

        if choice == 1:
            # 指定单个日期
            date_str = get_date_input("请输入要打卡的日期")
            if date_str == 'q':
                continue
            process_single_day(userId, sessionId, date_str)

        elif choice == 2:
            # 指定日期范围
            start_date = get_date_input("请输入开始日期")
            if start_date == 'q':
                continue
            end_date = get_date_input("请输入结束日期")
            if end_date == 'q':
                continue
            process_date_range(userId, sessionId, start_date, end_date)

        elif choice == 3:
            # 从指定日期开始连续打卡
            start_date = get_date_input("请输入开始日期")
            if start_date == 'q':
                continue
            process_continuous_days(userId, sessionId, start_date)

        elif choice == 4:
            print(f"{Colors.GREEN}感谢使用课程打卡系统，再见!{Colors.END}")
            break


if __name__ == "__main__":
    main()