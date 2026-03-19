CXX = clang++
CXXFLAGS = -std=c++17 -Wall -Wextra
LDFLAGS = -lwinhttp

TARGET = client
SOURCES = main.cpp connection.cpp identifier.cpp
OBJECTS = $(SOURCES:.cpp=.o)

all: $(TARGET)

$(TARGET): $(OBJECTS)
	$(CXX) $(OBJECTS) -o $(TARGET) $(LDFLAGS)

%.o: %.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

clean:
	del /Q *.o *.exe 2>NUL || rm -f *.o $(TARGET)

run: $(TARGET)
	./$(TARGET)