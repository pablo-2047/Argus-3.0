#include <pybind11/pybind11.h>
#include <pybind11/stl.h> // <-- NEW: Include for C++/Python list/map conversion
#include <string>
#include <vector>
#include <map>
#include <regex>

namespace py = pybind11;

// Forward declarations
void scrape_url(struct ScrapeJob& job);
std::map<std::string, std::string> parallel_scrape(const std::vector<std::string>& urls);
std::vector<std::string> parallel_sherlock(const std::string& username);
struct HarvesterResults {
    std::vector<std::string> emails;
    std::vector<std::string> subdomains;
};
HarvesterResults parallel_harvester(const std::string& domain);

// This creates the Python module
PYBIND11_MODULE(argus_cpp_core, m) {
    m.doc() = "ARGUS C++ Core: High-performance modules"; 
    
    // --- NEW: Expose the parallel_scrape function ---
    // It will take a Python list[str] and return a Python dict[str, str]
    m.def("parallel_scrape", &parallel_scrape, 
          "Scrapes a list of URLs in parallel using TBB and libcurl",
          py::arg("urls"));

    m.def("parallel_sherlock", &parallel_sherlock,
          "Checks for a username across top social sites in parallel",
          py::arg("username"));
    py::class_<HarvesterResults>(m, "HarvesterResults")
        .def(py::init<>())
        .def_readonly("emails", &HarvesterResults::emails)
        .def_readonly("subdomains", &HarvesterResults::subdomains);

    // --- NEW: Expose the parallel_harvester function ---
    m.def("parallel_harvester", &parallel_harvester,
          "Scrapes search engines for emails and subdomains in parallel",
          py::arg("domain"));
}