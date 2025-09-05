# 这是一个示例Python文件，用于演示代码审查功能

class Calculator:
    def __init__(self):
        self.result = 0
    
    def add(self, a, b):
        """加法运算"""
        self.result = a + b
        return self.result
    
    def subtract(self, a, b):
        """减法运算"""
        return a - b
    
    def multiply(self, a, b):
        """乘法运算"""
        return a * b
    
    def divide(self, a, b):
        """除法运算"""
        # 这里有一个潜在的问题：没有检查除数是否为0
        return a / b

# 全局变量
counter = 0

# 没有文档字符串的函数
def process_data(data):
    global counter
    result = []
    for item in data:
        counter += 1
        if item > 0:
            result.append(item * 2)
        else:
            result.append(item)
    return result

# 示例使用
if __name__ == "__main__":
    calc = Calculator()
    print(f"10 + 5 = {calc.add(10, 5)}")
    print(f"10 - 5 = {calc.subtract(10, 5)}")
    print(f"10 * 5 = {calc.multiply(10, 5)}")
    # 这里会导致错误
    try:
        print(f"10 / 0 = {calc.divide(10, 0)}")
    except ZeroDivisionError as e:
        print(f"错误: {e}")
    
    data = [1, -2, 3, -4, 5]
    processed_data = process_data(data)
    print(f"处理后的数据: {processed_data}")
    print(f"计数器: {counter}")