#include "global.hpp"
#include <iostream>
using namespace std;
unsigned long long measure(unsigned long long (*func)()) {
    LARGE_INTEGER freq, start, end;

    QueryPerformanceFrequency(&freq);
    QueryPerformanceCounter(&start);

    unsigned long long retval = func();

    QueryPerformanceCounter(&end);
    double time = (double)(end.QuadPart - start.QuadPart) / freq.QuadPart;
    cout << "Time: " << time << " seconds (Execution)\n";
    return retval;
}