#include "observer_candidate.hpp"

#include <windows.h>
#include <winsvc.h>

namespace {

SERVICE_STATUS_HANDLE g_status_handle = nullptr;
SERVICE_STATUS g_status{};

void ReportStatus(DWORD state, DWORD win32_exit, DWORD service_exit) noexcept {
  if (g_status_handle == nullptr) {
    return;
  }
  g_status.dwServiceType = SERVICE_WIN32_OWN_PROCESS;
  g_status.dwCurrentState = state;
  g_status.dwControlsAccepted = 0;
  g_status.dwWin32ExitCode = win32_exit;
  g_status.dwServiceSpecificExitCode = service_exit;
  g_status.dwCheckPoint = 0;
  g_status.dwWaitHint = 0;
  SetServiceStatus(g_status_handle, &g_status);
}

DWORD WINAPI ControlHandler(DWORD, DWORD, void*, void*) noexcept {
  // This bounded one-shot candidate does not accept mutable controls. It
  // reports a terminal NO_GO immediately after observation.
  return NO_ERROR;
}

void WINAPI ServiceMain(DWORD argc, LPWSTR* argv) noexcept {
  g_status_handle = RegisterServiceCtrlHandlerExW(
      p0::owner_observer::kServiceName, ControlHandler, nullptr);
  if (g_status_handle == nullptr) {
    return;
  }
  if (argc != 1 || argv == nullptr || argv[0] == nullptr ||
      CompareStringOrdinal(argv[0], -1, p0::owner_observer::kServiceName, -1,
                           TRUE) != CSTR_EQUAL) {
    ReportStatus(SERVICE_STOPPED, ERROR_INVALID_PARAMETER, 3);
    return;
  }
  ReportStatus(SERVICE_START_PENDING, NO_ERROR, 0);
  ReportStatus(SERVICE_RUNNING, NO_ERROR, 0);
  const auto observation = p0::owner_observer::ObserveServiceCandidate();
  const bool unexpectedly_authoritative =
      observation.owner_authority_verified ||
      observation.actual_authority_granted || observation.production_approval ||
      observation.full_scan_approval || observation.p0_phase_exit ||
      observation.action_applied;
  ReportStatus(SERVICE_STOPPED, ERROR_SERVICE_SPECIFIC_ERROR,
               unexpectedly_authoritative ? 2U : 1U);
}

}  // namespace

int wmain() {
  SERVICE_TABLE_ENTRYW table[] = {
      {const_cast<LPWSTR>(p0::owner_observer::kServiceName), ServiceMain},
      {nullptr, nullptr},
  };
  if (!StartServiceCtrlDispatcherW(table)) {
    return static_cast<int>(GetLastError());
  }
  return ERROR_SUCCESS;
}
