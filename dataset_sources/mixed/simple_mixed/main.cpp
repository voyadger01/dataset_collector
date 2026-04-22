extern "C" {
    int add(int a, int b);
    int multiply(int a, int b);
    void print_result(const char* operation, int result);
}

#include <iostream>

int main() {
    int a = 10, b = 5;
    
    int sum = add(a, b);
    int product = multiply(a, b);
    
    std::cout << "C++: a=" << a << ", b=" << b << std::endl;
    
    print_result("Sum (C)", sum);
    print_result("Product (C)", product);
    
    return 0;
}