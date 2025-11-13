cmake_minimum_required(VERSION 3.10)
project(argus_cpp_core)

# Find Python, PyBind11, and vcpkg
set(CMAKE_TOOLCHAIN_FILE "C:/ARGUS/vcpkg/scripts/buildsystems/vcpkg.cmake") # <-- Make sure this path is correct
find_package(Python3 COMPONENTS Interpreter Development REQUIRED)
find_package(pybind11 REQUIRED)

# Find cURL and TBB
find_package(CURL REQUIRED)
find_package(TBB REQUIRED) # <-- NEW: Find TBB

# Define our C++ sources
set(SOURCES
    fast_scraper.cpp
    bindings.cpp
)

# Create the Python module
pybind11_add_module(argus_cpp_core ${SOURCES})
target_compile_definitions(argus_cpp_core PRIVATE NOMINMAX)

# Link the libraries
target_link_libraries(argus_cpp_core PRIVATE 
    CURL::libcurl
    TBB::tbb       # <-- NEW: Link TBB
)