def positive_integer_checker(string):
    if string.isnumeric():
        return int(string)
    else:
        try:
            for char in string.split('.')[1]:
                if char != '0':
                    return False
                return int(float(string))
        except:
            return False

a = "42"
b = "42.00"
c = "abc"

print(positive_integer_checker(a))
print(positive_integer_checker(b))
print(positive_integer_checker(c))
