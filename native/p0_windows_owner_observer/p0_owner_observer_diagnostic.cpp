#include "observer_candidate.hpp"

#include <windows.h>

#include <cstdio>
#include <string>

int wmain(int argc, wchar_t*[]) {
  if (argc != 1) {
    return ERROR_INVALID_PARAMETER;
  }
  const auto observation = p0::owner_observer::ObserveDiagnosticCandidate();
  const std::string json = p0::owner_observer::DiagnosticJson(observation);
  if (std::fwrite(json.data(), 1, json.size(), stdout) != json.size() ||
      std::fputc('\n', stdout) == EOF) {
    return ERROR_WRITE_FAULT;
  }
  return ERROR_SUCCESS;
}
