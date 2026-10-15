#include "observer_candidate.hpp"

#include <windows.h>
#include <bcrypt.h>
#include <sddl.h>
#include <winsvc.h>
#include <wldp.h>

#include <algorithm>
#include <array>
#include <cctype>
#include <cstring>
#include <iomanip>
#include <limits>
#include <memory>
#include <sstream>
#include <string_view>
#include <utility>

namespace p0::owner_observer {
namespace {

constexpr DWORD kServiceSidInfoLevel = 5;
constexpr DWORD kServiceSidTypeRestricted = 3;
constexpr std::uint64_t kMaxCandidateImageBytes = 256ULL * 1024ULL * 1024ULL;
constexpr wchar_t kExpectedImageSuffix[] =
    L"\\Program Files\\llm-novel-dc\\owner-verifier-v2\\"
    L"llm-novel-dc-owner-verifier.exe";

class UniqueHandle {
 public:
  UniqueHandle() = default;
  explicit UniqueHandle(HANDLE value) noexcept : value_(value) {}
  ~UniqueHandle() {
    if (valid()) {
      CloseHandle(value_);
    }
  }
  UniqueHandle(const UniqueHandle&) = delete;
  UniqueHandle& operator=(const UniqueHandle&) = delete;
  UniqueHandle(UniqueHandle&& other) noexcept : value_(other.release()) {}
  UniqueHandle& operator=(UniqueHandle&& other) noexcept {
    if (this != &other) {
      if (valid()) {
        CloseHandle(value_);
      }
      value_ = other.release();
    }
    return *this;
  }
  [[nodiscard]] bool valid() const noexcept {
    return value_ != nullptr && value_ != INVALID_HANDLE_VALUE;
  }
  [[nodiscard]] HANDLE get() const noexcept { return value_; }

 private:
  HANDLE release() noexcept {
    HANDLE value = value_;
    value_ = nullptr;
    return value;
  }
  HANDLE value_{nullptr};
};

class UniqueServiceHandle {
 public:
  UniqueServiceHandle() = default;
  explicit UniqueServiceHandle(SC_HANDLE value) noexcept : value_(value) {}
  ~UniqueServiceHandle() {
    if (value_ != nullptr) {
      CloseServiceHandle(value_);
    }
  }
  UniqueServiceHandle(const UniqueServiceHandle&) = delete;
  UniqueServiceHandle& operator=(const UniqueServiceHandle&) = delete;
  [[nodiscard]] SC_HANDLE get() const noexcept { return value_; }
  [[nodiscard]] bool valid() const noexcept { return value_ != nullptr; }

 private:
  SC_HANDLE value_{nullptr};
};

class UniqueModule {
 public:
  UniqueModule() = default;
  explicit UniqueModule(HMODULE value) noexcept : value_(value) {}
  ~UniqueModule() {
    if (value_ != nullptr) {
      FreeLibrary(value_);
    }
  }
  UniqueModule(const UniqueModule&) = delete;
  UniqueModule& operator=(const UniqueModule&) = delete;
  [[nodiscard]] HMODULE get() const noexcept { return value_; }

 private:
  HMODULE value_{nullptr};
};

class UniqueAlgorithm {
 public:
  ~UniqueAlgorithm() {
    if (value != nullptr) {
      BCryptCloseAlgorithmProvider(value, 0);
    }
  }
  BCRYPT_ALG_HANDLE value{nullptr};
};

class UniqueHash {
 public:
  ~UniqueHash() {
    if (value != nullptr) {
      BCryptDestroyHash(value);
    }
  }
  BCRYPT_HASH_HANDLE value{nullptr};
};

void AddError(CandidateObservation& result, std::string text) {
  result.diagnostic_errors.push_back(std::move(text));
}

std::string HexBytes(const BYTE* bytes, std::size_t size) {
  static constexpr char kHex[] = "0123456789abcdef";
  std::string output(size * 2, '0');
  for (std::size_t index = 0; index < size; ++index) {
    output[index * 2] = kHex[(bytes[index] >> 4U) & 0x0fU];
    output[index * 2 + 1] = kHex[bytes[index] & 0x0fU];
  }
  return output;
}

bool Sha256Bytes(const BYTE* bytes, std::size_t size, std::string& output) {
  UniqueAlgorithm algorithm;
  if (!BCRYPT_SUCCESS(BCryptOpenAlgorithmProvider(
          &algorithm.value, BCRYPT_SHA256_ALGORITHM, MS_PRIMITIVE_PROVIDER, 0))) {
    return false;
  }
  DWORD object_length = 0;
  DWORD hash_length = 0;
  DWORD returned = 0;
  if (!BCRYPT_SUCCESS(BCryptGetProperty(
          algorithm.value, BCRYPT_OBJECT_LENGTH,
          reinterpret_cast<PUCHAR>(&object_length), sizeof(object_length),
          &returned, 0)) ||
      returned != sizeof(object_length) || object_length == 0 ||
      !BCRYPT_SUCCESS(BCryptGetProperty(
          algorithm.value, BCRYPT_HASH_LENGTH,
          reinterpret_cast<PUCHAR>(&hash_length), sizeof(hash_length),
          &returned, 0)) ||
      returned != sizeof(hash_length) || hash_length != 32) {
    return false;
  }
  std::vector<BYTE> object(object_length);
  std::array<BYTE, 32> digest{};
  UniqueHash hash;
  if (!BCRYPT_SUCCESS(BCryptCreateHash(
          algorithm.value, &hash.value, object.data(),
          static_cast<ULONG>(object.size()), nullptr, 0, 0))) {
    return false;
  }
  if (size > static_cast<std::size_t>(std::numeric_limits<ULONG>::max())) {
    return false;
  }
  if (size != 0 && !BCRYPT_SUCCESS(BCryptHashData(
                       hash.value, const_cast<PUCHAR>(bytes),
                       static_cast<ULONG>(size), 0))) {
    return false;
  }
  if (!BCRYPT_SUCCESS(BCryptFinishHash(
          hash.value, digest.data(), static_cast<ULONG>(digest.size()), 0))) {
    return false;
  }
  output = HexBytes(digest.data(), digest.size());
  return true;
}

bool Sha256Handle(HANDLE file, std::string& output) {
  LARGE_INTEGER size{};
  if (!GetFileSizeEx(file, &size) || size.QuadPart < 0 ||
      static_cast<std::uint64_t>(size.QuadPart) > kMaxCandidateImageBytes) {
    return false;
  }
  LARGE_INTEGER start{};
  if (!SetFilePointerEx(file, start, nullptr, FILE_BEGIN)) {
    return false;
  }
  UniqueAlgorithm algorithm;
  if (!BCRYPT_SUCCESS(BCryptOpenAlgorithmProvider(
          &algorithm.value, BCRYPT_SHA256_ALGORITHM, MS_PRIMITIVE_PROVIDER, 0))) {
    return false;
  }
  DWORD object_length = 0;
  DWORD hash_length = 0;
  DWORD returned = 0;
  if (!BCRYPT_SUCCESS(BCryptGetProperty(
          algorithm.value, BCRYPT_OBJECT_LENGTH,
          reinterpret_cast<PUCHAR>(&object_length), sizeof(object_length),
          &returned, 0)) ||
      returned != sizeof(object_length) || object_length == 0 ||
      !BCRYPT_SUCCESS(BCryptGetProperty(
          algorithm.value, BCRYPT_HASH_LENGTH,
          reinterpret_cast<PUCHAR>(&hash_length), sizeof(hash_length),
          &returned, 0)) ||
      returned != sizeof(hash_length) || hash_length != 32) {
    return false;
  }
  std::vector<BYTE> object(object_length);
  std::array<BYTE, 32> digest{};
  UniqueHash hash;
  if (!BCRYPT_SUCCESS(BCryptCreateHash(
          algorithm.value, &hash.value, object.data(),
          static_cast<ULONG>(object.size()), nullptr, 0, 0))) {
    return false;
  }
  std::array<BYTE, 64 * 1024> buffer{};
  std::uint64_t total = 0;
  for (;;) {
    DWORD read = 0;
    if (!ReadFile(file, buffer.data(), static_cast<DWORD>(buffer.size()), &read,
                  nullptr)) {
      return false;
    }
    if (read == 0) {
      break;
    }
    total += read;
    if (total > static_cast<std::uint64_t>(size.QuadPart) ||
        !BCRYPT_SUCCESS(BCryptHashData(hash.value, buffer.data(), read, 0))) {
      return false;
    }
  }
  if (total != static_cast<std::uint64_t>(size.QuadPart) ||
      !BCRYPT_SUCCESS(BCryptFinishHash(
          hash.value, digest.data(), static_cast<ULONG>(digest.size()), 0))) {
    return false;
  }
  output = HexBytes(digest.data(), digest.size());
  return true;
}

struct StableFileTuple {
  FILE_ID_INFO id{};
  FILE_BASIC_INFO basic{};
  FILE_STANDARD_INFO standard{};
};

bool QueryFileTuple(HANDLE file, StableFileTuple& value) {
  return GetFileInformationByHandleEx(file, FileIdInfo, &value.id,
                                      sizeof(value.id)) &&
         GetFileInformationByHandleEx(file, FileBasicInfo, &value.basic,
                                      sizeof(value.basic)) &&
         GetFileInformationByHandleEx(file, FileStandardInfo, &value.standard,
                                      sizeof(value.standard));
}

bool SameFileTuple(const StableFileTuple& left, const StableFileTuple& right) {
  return left.id.VolumeSerialNumber == right.id.VolumeSerialNumber &&
         std::memcmp(left.id.FileId.Identifier, right.id.FileId.Identifier,
                     sizeof(left.id.FileId.Identifier)) == 0 &&
         left.basic.CreationTime.QuadPart == right.basic.CreationTime.QuadPart &&
         left.basic.LastWriteTime.QuadPart == right.basic.LastWriteTime.QuadPart &&
         left.basic.ChangeTime.QuadPart == right.basic.ChangeTime.QuadPart &&
         left.basic.FileAttributes == right.basic.FileAttributes &&
         left.standard.EndOfFile.QuadPart == right.standard.EndOfFile.QuadPart &&
         left.standard.NumberOfLinks == right.standard.NumberOfLinks &&
         left.standard.Directory == right.standard.Directory;
}

std::wstring FinalPath(HANDLE file) {
  DWORD required = GetFinalPathNameByHandleW(
      file, nullptr, 0, FILE_NAME_NORMALIZED | VOLUME_NAME_GUID);
  if (required == 0 || required > 32768) {
    return {};
  }
  std::vector<wchar_t> buffer(static_cast<std::size_t>(required) + 1U, L'\0');
  DWORD written = GetFinalPathNameByHandleW(
      file, buffer.data(), static_cast<DWORD>(buffer.size()),
      FILE_NAME_NORMALIZED | VOLUME_NAME_GUID);
  if (written == 0 || written >= buffer.size()) {
    return {};
  }
  return std::wstring(buffer.data(), written);
}

FileObservation ObserveFile(const std::wstring& path,
                            CandidateObservation& parent,
                            const char* label,
                            bool require_single_link = true) {
  FileObservation result;
  result.path = path;
  UniqueHandle file(CreateFileW(
      path.c_str(), GENERIC_READ | READ_CONTROL, FILE_SHARE_READ, nullptr,
      OPEN_EXISTING,
      FILE_ATTRIBUTE_NORMAL | FILE_FLAG_OPEN_REPARSE_POINT |
          FILE_FLAG_SEQUENTIAL_SCAN,
      nullptr));
  if (!file.valid()) {
    AddError(parent, std::string(label) + ":open_failed");
    return result;
  }
  DWORD flags = 0;
  if (!GetHandleInformation(file.get(), &flags) ||
      (flags & HANDLE_FLAG_INHERIT) != 0) {
    AddError(parent, std::string(label) + ":inheritable_or_unqueryable_handle");
    return result;
  }
  StableFileTuple before{};
  StableFileTuple after{};
  FILE_ATTRIBUTE_TAG_INFO tags{};
  if (!QueryFileTuple(file.get(), before) || before.standard.Directory ||
      !GetFileInformationByHandleEx(file.get(), FileAttributeTagInfo, &tags,
                                    sizeof(tags))) {
    AddError(parent, std::string(label) + ":identity_query_failed");
    return result;
  }
  result.no_reparse = (tags.FileAttributes & FILE_ATTRIBUTE_REPARSE_POINT) == 0;
  result.single_link = before.standard.NumberOfLinks == 1;
  result.final_volume_guid_path = FinalPath(file.get());
  result.volume_serial = before.id.VolumeSerialNumber;
  result.file_id_128_hex = HexBytes(before.id.FileId.Identifier,
                                    sizeof(before.id.FileId.Identifier));
  if (result.final_volume_guid_path.empty() ||
      !Sha256Handle(file.get(), result.sha256) ||
      !QueryFileTuple(file.get(), after)) {
    AddError(parent, std::string(label) + ":content_or_post_identity_failed");
    return result;
  }
  result.identity_stable = SameFileTuple(before, after);
  result.observed = result.no_reparse &&
                    (!require_single_link || result.single_link) &&
                    result.identity_stable && result.sha256.size() == 64;
  if (!result.observed) {
    AddError(parent, std::string(label) + ":strict_file_contract_not_met");
  }
  return result;
}

std::wstring CurrentImagePath() {
  std::vector<wchar_t> buffer(32768, L'\0');
  DWORD written = GetModuleFileNameW(nullptr, buffer.data(),
                                     static_cast<DWORD>(buffer.size()));
  if (written == 0 || written >= buffer.size()) {
    return {};
  }
  return std::wstring(buffer.data(), written);
}

std::vector<BYTE> TokenInformation(HANDLE token,
                                   TOKEN_INFORMATION_CLASS info_class) {
  DWORD required = 0;
  if (GetTokenInformation(token, info_class, nullptr, 0, &required) ||
      GetLastError() != ERROR_INSUFFICIENT_BUFFER || required == 0 ||
      required > 1024 * 1024) {
    return {};
  }
  std::vector<BYTE> buffer(required);
  if (!GetTokenInformation(token, info_class, buffer.data(), required,
                           &required)) {
    return {};
  }
  return buffer;
}

bool SidInGroups(const TOKEN_GROUPS* groups, PSID expected,
                 bool require_enabled) {
  if (groups == nullptr || expected == nullptr) {
    return false;
  }
  for (DWORD index = 0; index < groups->GroupCount; ++index) {
    const SID_AND_ATTRIBUTES& item = groups->Groups[index];
    if (EqualSid(item.Sid, expected)) {
      if (!require_enabled) {
        return true;
      }
      return (item.Attributes & SE_GROUP_ENABLED) != 0 &&
             (item.Attributes & SE_GROUP_USE_FOR_DENY_ONLY) == 0;
    }
  }
  return false;
}

void ObserveCurrentToken(CandidateObservation& result) {
  HANDLE raw = nullptr;
  if (!OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &raw)) {
    AddError(result, "token:open_failed");
    return;
  }
  UniqueHandle token(raw);
  const auto user_bytes = TokenInformation(token.get(), TokenUser);
  const auto group_bytes = TokenInformation(token.get(), TokenGroups);
  const auto restricted_bytes = TokenInformation(token.get(), TokenRestrictedSids);
  const auto integrity_bytes = TokenInformation(token.get(), TokenIntegrityLevel);
  if (user_bytes.empty() || group_bytes.empty() || restricted_bytes.empty() ||
      integrity_bytes.empty()) {
    AddError(result, "token:required_projection_failed");
    return;
  }
  const auto* user = reinterpret_cast<const TOKEN_USER*>(user_bytes.data());
  LPWSTR user_sid_text = nullptr;
  if (ConvertSidToStringSidW(user->User.Sid, &user_sid_text)) {
    result.token_user_sid = user_sid_text;
    LocalFree(user_sid_text);
  }
  PSID expected_service_sid = nullptr;
  if (!ConvertStringSidToSidW(kExpectedServiceSid, &expected_service_sid)) {
    AddError(result, "token:compiled_service_sid_invalid");
    return;
  }
  result.token_user_is_local_system = IsWellKnownSid(user->User.Sid, WinLocalSystemSid) != FALSE;
  result.service_sid_enabled = SidInGroups(
      reinterpret_cast<const TOKEN_GROUPS*>(group_bytes.data()),
      expected_service_sid, true);
  result.service_sid_restricted = SidInGroups(
      reinterpret_cast<const TOKEN_GROUPS*>(restricted_bytes.data()),
      expected_service_sid, true);
  LocalFree(expected_service_sid);

  TOKEN_TYPE token_type = TokenImpersonation;
  DWORD returned = 0;
  result.token_primary =
      GetTokenInformation(token.get(), TokenType, &token_type,
                          sizeof(token_type), &returned) &&
      returned == sizeof(token_type) && token_type == TokenPrimary;

  const auto* integrity =
      reinterpret_cast<const TOKEN_MANDATORY_LABEL*>(integrity_bytes.data());
  const DWORD sub_count = *GetSidSubAuthorityCount(integrity->Label.Sid);
  result.token_system_integrity =
      sub_count != 0 &&
      *GetSidSubAuthority(integrity->Label.Sid, sub_count - 1) >=
          SECURITY_MANDATORY_SYSTEM_RID;

  TOKEN_LINKED_TOKEN linked{};
  if (GetTokenInformation(token.get(), TokenLinkedToken, &linked,
                          sizeof(linked), &returned)) {
    if (linked.LinkedToken != nullptr) {
      CloseHandle(linked.LinkedToken);
    }
    result.token_linked_absent = false;
  } else {
    result.token_linked_absent = GetLastError() == ERROR_NO_SUCH_LOGON_SESSION;
  }
  result.current_process_token_observed = true;
}

bool IsStringResource(LPCWSTR value, std::wstring_view expected) {
  return !IS_INTRESOURCE(value) &&
         CompareStringOrdinal(value, -1, expected.data(),
                              static_cast<int>(expected.size()), FALSE) ==
             CSTR_EQUAL;
}

struct ResourceCount {
  DWORD types{0};
  DWORD total_names{0};
  DWORD names{0};
  DWORD total_languages{0};
  DWORD languages{0};
};

BOOL CALLBACK CountType(HMODULE, LPWSTR type, LONG_PTR context) {
  auto* count = reinterpret_cast<ResourceCount*>(context);
  if (IsStringResource(type, kBootstrapResourceType)) {
    ++count->types;
  }
  return TRUE;
}

BOOL CALLBACK CountName(HMODULE, LPCWSTR, LPWSTR name, LONG_PTR context) {
  auto* count = reinterpret_cast<ResourceCount*>(context);
  ++count->total_names;
  if (IsStringResource(name, kBootstrapResourceName)) {
    ++count->names;
  }
  return TRUE;
}

BOOL CALLBACK CountLanguage(HMODULE, LPCWSTR, LPCWSTR, WORD language,
                            LONG_PTR context) {
  auto* count = reinterpret_cast<ResourceCount*>(context);
  ++count->total_languages;
  if (language == MAKELANGID(LANG_NEUTRAL, SUBLANG_NEUTRAL)) {
    ++count->languages;
  }
  return TRUE;
}

void ObserveBootstrapResource(HMODULE module, CandidateObservation& result) {
  if (module == nullptr) {
    AddError(result, "resource:self_module_missing");
    return;
  }
  ResourceCount count{};
  if (!EnumResourceTypesExW(module, CountType,
                            reinterpret_cast<LONG_PTR>(&count),
                            RESOURCE_ENUM_LN, 0) ||
      !EnumResourceNamesExW(
          module, const_cast<LPWSTR>(kBootstrapResourceType), CountName,
          reinterpret_cast<LONG_PTR>(&count), RESOURCE_ENUM_LN, 0) ||
      !EnumResourceLanguagesExW(
          module, const_cast<LPCWSTR>(kBootstrapResourceType),
          const_cast<LPCWSTR>(kBootstrapResourceName), CountLanguage,
          reinterpret_cast<LONG_PTR>(&count), RESOURCE_ENUM_LN, 0)) {
    AddError(result, "resource:enumeration_failed");
    return;
  }
  HRSRC resource = FindResourceExW(
      module, kBootstrapResourceType, kBootstrapResourceName,
      MAKELANGID(LANG_NEUTRAL, SUBLANG_NEUTRAL));
  if (resource == nullptr) {
    AddError(result, "resource:exact_selector_missing");
    return;
  }
  const DWORD size = SizeofResource(module, resource);
  HGLOBAL loaded = LoadResource(module, resource);
  const BYTE* bytes = loaded == nullptr
                          ? nullptr
                          : static_cast<const BYTE*>(LockResource(loaded));
  if (bytes == nullptr || size == 0 ||
      !Sha256Bytes(bytes, size, result.bootstrap_resource_sha256)) {
    AddError(result, "resource:bytes_hash_failed");
    return;
  }
  result.bootstrap_resource_exact =
      count.types == 1 && count.total_names == 1 && count.names == 1 &&
      count.total_languages == 1 && count.languages == 1;
  if (!result.bootstrap_resource_exact) {
    AddError(result, "resource:selector_not_exact_one");
  }
}

std::wstring SiblingServicePath(const std::wstring& diagnostic_path) {
  const std::size_t separator = diagnostic_path.find_last_of(L"\\/");
  if (separator == std::wstring::npos) {
    return {};
  }
  std::wstring result = diagnostic_path.substr(0, separator + 1);
  result.append(L"llm-novel-dc-owner-verifier.exe");
  return result;
}

bool EqualPath(const std::wstring& left, const std::wstring& right) {
  return CompareStringOrdinal(left.c_str(), static_cast<int>(left.size()),
                              right.c_str(), static_cast<int>(right.size()),
                              TRUE) == CSTR_EQUAL;
}

bool EndsWithPath(const std::wstring& value, std::wstring_view suffix) {
  if (value.size() < suffix.size()) {
    return false;
  }
  return CompareStringOrdinal(
             value.data() + (value.size() - suffix.size()),
             static_cast<int>(suffix.size()), suffix.data(),
             static_cast<int>(suffix.size()), TRUE) == CSTR_EQUAL;
}

ModuleObservation ObserveLoadedModule(const char* role,
                                      const wchar_t* name,
                                      CandidateObservation& parent) {
  ModuleObservation result;
  result.role = role;
  result.expected_name = name;
  std::vector<wchar_t> system_directory(32768, L'\0');
  UINT system_written = GetSystemDirectoryW(
      system_directory.data(), static_cast<UINT>(system_directory.size()));
  if (system_written == 0 || system_written >= system_directory.size()) {
    AddError(parent, std::string("module:") + role + ":system32_failed");
    return result;
  }
  system_directory.resize(system_written);
  std::wstring expected_path(system_directory.data(), system_directory.size());
  expected_path.push_back(L'\\');
  expected_path.append(name);
  HMODULE module = nullptr;
  if (!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                          expected_path.c_str(), &module) || module == nullptr) {
    AddError(parent, std::string("module:") + role + ":exact_mapping_not_loaded");
    return result;
  }
  std::vector<wchar_t> path_buffer(32768, L'\0');
  DWORD written = GetModuleFileNameW(module, path_buffer.data(),
                                     static_cast<DWORD>(path_buffer.size()));
  if (written == 0 || written >= path_buffer.size()) {
    AddError(parent, std::string("module:") + role + ":path_failed");
    return result;
  }
  const std::wstring path(path_buffer.data(), written);
  result.loaded = true;
  result.system32_path = EqualPath(path, expected_path);
  result.file = ObserveFile(path, parent, role, false);
  if (!result.system32_path) {
    AddError(parent, std::string("module:") + role + ":not_system32");
  }
  return result;
}

void ObserveLoadedCryptoModules(CandidateObservation& result) {
  // Force a bounded CNG operation through the fixed primitive provider before
  // observing the process loader's module set.
  std::string discarded;
  const BYTE marker[] = {0x50, 0x30};
  if (!Sha256Bytes(marker, sizeof(marker), discarded)) {
    AddError(result, "module:cng_primitive_probe_failed");
  }
  result.modules.push_back(
      ObserveLoadedModule("BCRYPT", L"bcrypt.dll", result));
  result.modules.push_back(ObserveLoadedModule(
      "BCRYPT_PRIMITIVES", L"bcryptprimitives.dll", result));
}

void ObserveWldp(CandidateObservation& result) {
  UniqueModule module(LoadLibraryExW(L"wldp.dll", nullptr,
                                     LOAD_LIBRARY_SEARCH_SYSTEM32));
  if (module.get() == nullptr) {
    AddError(result, "wldp:system32_load_failed");
    return;
  }
  using GetPolicyFn = HRESULT(WINAPI*)(PWLDP_HOST_INFORMATION, PDWORD, DWORD);
  using QueryModeFn = HRESULT(WINAPI*)(PWLDP_WINDOWS_LOCKDOWN_MODE);
  auto get_policy = reinterpret_cast<GetPolicyFn>(
      GetProcAddress(module.get(), "WldpGetLockdownPolicy"));
  auto query_mode = reinterpret_cast<QueryModeFn>(
      GetProcAddress(module.get(), "WldpQueryWindowsLockdownMode"));
  if (get_policy == nullptr || query_mode == nullptr) {
    AddError(result, "wldp:required_export_missing");
    return;
  }
  DWORD state = 0;
  WLDP_WINDOWS_LOCKDOWN_MODE mode = WLDP_WINDOWS_LOCKDOWN_MODE_MAX;
  WLDP_HOST_INFORMATION host{};
  host.dwRevision = WLDP_HOST_INFORMATION_REVISION;
  host.dwHostId = WLDP_HOST_ID_GLOBAL;
  host.szSource = nullptr;
  host.hSource = nullptr;
  const HRESULT policy_hr = get_policy(&host, &state, 0);
  const HRESULT mode_hr = query_mode(&mode);
  if (FAILED(policy_hr) || FAILED(mode_hr)) {
    AddError(result, "wldp:query_failed");
    return;
  }
  result.wldp_query_succeeded = true;
  result.wldp_lockdown_state = state;
  result.wldp_windows_lockdown_mode = static_cast<std::int32_t>(mode);
  result.wdac_umci_enforced = WLDP_LOCKDOWN_IS_UMCIENFORCE(state) != FALSE;
}

bool ExactQuotedNoArgumentPath(const std::wstring& value) {
  return value.size() >= 3 && value.front() == L'\"' &&
         value.back() == L'\"' &&
         value.find(L'\"', 1) == value.size() - 1;
}

void ObserveFixedService(CandidateObservation& result) {
  UniqueServiceHandle manager(
      OpenSCManagerW(nullptr, nullptr, SC_MANAGER_CONNECT));
  if (!manager.valid()) {
    AddError(result, "service:scm_open_failed");
    return;
  }
  UniqueServiceHandle service(OpenServiceW(
      manager.get(), kServiceName, SERVICE_QUERY_CONFIG | SERVICE_QUERY_STATUS));
  if (!service.valid()) {
    if (GetLastError() != ERROR_SERVICE_DOES_NOT_EXIST) {
      AddError(result, "service:fixed_service_open_failed");
    }
    return;
  }
  result.service_present = true;
  SERVICE_STATUS_PROCESS status{};
  DWORD returned = 0;
  if (QueryServiceStatusEx(service.get(), SC_STATUS_PROCESS_INFO,
                           reinterpret_cast<LPBYTE>(&status), sizeof(status),
                           &returned)) {
    result.service_running = status.dwCurrentState == SERVICE_RUNNING &&
                             status.dwProcessId != 0;
    result.service_pid = status.dwProcessId;
    result.service_process_is_self =
        result.production_binary &&
        status.dwProcessId == GetCurrentProcessId();
  } else {
    AddError(result, "service:status_query_failed");
  }
  DWORD required = 0;
  QueryServiceConfigW(service.get(), nullptr, 0, &required);
  if (GetLastError() != ERROR_INSUFFICIENT_BUFFER ||
      required < sizeof(QUERY_SERVICE_CONFIGW) || required > 64 * 1024) {
    AddError(result, "service:config_size_failed");
    return;
  }
  std::vector<BYTE> config_bytes(required);
  auto* config = reinterpret_cast<QUERY_SERVICE_CONFIGW*>(config_bytes.data());
  if (!QueryServiceConfigW(service.get(), config, required, &required)) {
    AddError(result, "service:config_query_failed");
    return;
  }
  DWORD sid_required = 0;
  QueryServiceConfig2W(service.get(), kServiceSidInfoLevel, nullptr, 0,
                       &sid_required);
  if (GetLastError() != ERROR_INSUFFICIENT_BUFFER ||
      sid_required < sizeof(SERVICE_SID_INFO) || sid_required > 4096) {
    AddError(result, "service:sid_size_failed");
    return;
  }
  std::vector<BYTE> sid_bytes(sid_required);
  if (!QueryServiceConfig2W(service.get(), kServiceSidInfoLevel,
                            sid_bytes.data(), sid_required, &sid_required)) {
    AddError(result, "service:sid_query_failed");
    return;
  }
  const auto* sid_info =
      reinterpret_cast<const SERVICE_SID_INFO*>(sid_bytes.data());
  const std::wstring binary = config->lpBinaryPathName == nullptr
                                  ? L""
                                  : config->lpBinaryPathName;
  const std::wstring account = config->lpServiceStartName == nullptr
                                   ? L""
                                   : config->lpServiceStartName;
  const std::wstring unquoted_binary =
      ExactQuotedNoArgumentPath(binary)
          ? binary.substr(1, binary.size() - 2)
          : L"";
  result.service_shape_candidate_config_matches =
      config->dwServiceType == SERVICE_WIN32_OWN_PROCESS &&
      config->dwStartType == SERVICE_DEMAND_START &&
      config->dwErrorControl == SERVICE_ERROR_NORMAL &&
      (EqualPath(account, L"LocalSystem") ||
       EqualPath(account, L"NT AUTHORITY\\SYSTEM")) &&
      sid_info->dwServiceSidType == kServiceSidTypeRestricted &&
      !unquoted_binary.empty() &&
      EndsWithPath(unquoted_binary, kExpectedImageSuffix);
}

std::string WideToUtf8(const std::wstring& value) {
  if (value.empty()) {
    return {};
  }
  const int size = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS,
                                       value.data(),
                                       static_cast<int>(value.size()), nullptr,
                                       0, nullptr, nullptr);
  if (size <= 0) {
    return {};
  }
  std::string output(static_cast<std::size_t>(size), '\0');
  if (WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, value.data(),
                          static_cast<int>(value.size()), output.data(), size,
                          nullptr, nullptr) != size) {
    return {};
  }
  return output;
}

std::string JsonEscape(const std::string& value) {
  std::ostringstream output;
  for (const unsigned char byte : value) {
    switch (byte) {
      case '\"': output << "\\\""; break;
      case '\\': output << "\\\\"; break;
      case '\b': output << "\\b"; break;
      case '\f': output << "\\f"; break;
      case '\n': output << "\\n"; break;
      case '\r': output << "\\r"; break;
      case '\t': output << "\\t"; break;
      default:
        if (byte < 0x20) {
          output << "\\u" << std::hex << std::setw(4) << std::setfill('0')
                 << static_cast<unsigned int>(byte) << std::dec;
        } else {
          output << static_cast<char>(byte);
        }
    }
  }
  return output.str();
}

const char* JsonBool(bool value) { return value ? "true" : "false"; }

void AppendFileJson(std::ostringstream& out, const FileObservation& file) {
  out << "{\"observed\":" << JsonBool(file.observed)
      << ",\"no_reparse\":" << JsonBool(file.no_reparse)
      << ",\"single_link\":" << JsonBool(file.single_link)
      << ",\"identity_stable\":" << JsonBool(file.identity_stable)
      << ",\"path\":\"" << JsonEscape(WideToUtf8(file.path))
      << "\",\"final_volume_guid_path\":\""
      << JsonEscape(WideToUtf8(file.final_volume_guid_path))
      << "\",\"volume_serial_decimal\":\"" << file.volume_serial
      << "\",\"file_id_128_hex\":\"" << file.file_id_128_hex
      << "\",\"sha256\":\"" << file.sha256 << "\"}";
}

}  // namespace

CandidateObservation ObserveBoundedCandidateInternal(
    bool production_binary) noexcept {
  CandidateObservation result;
  result.production_binary = production_binary;
  result.candidate_only = true;
  try {
    result.process_id = GetCurrentProcessId();
    LARGE_INTEGER qpc_frequency{};
    LARGE_INTEGER qpc_start{};
    FILETIME creation_start{}, exit_start{}, kernel_start{}, user_start{};
    const bool interval_start_ok =
        QueryPerformanceFrequency(&qpc_frequency) &&
        QueryPerformanceCounter(&qpc_start) &&
        GetProcessTimes(GetCurrentProcess(), &creation_start, &exit_start,
                        &kernel_start, &user_start);
    result.qpc_frequency = qpc_frequency.QuadPart;
    result.qpc_start = qpc_start.QuadPart;
    result.process_creation_time_100ns =
        (static_cast<std::uint64_t>(creation_start.dwHighDateTime) << 32U) |
        creation_start.dwLowDateTime;
    ObserveCurrentToken(result);
    const std::wstring image = CurrentImagePath();
    if (image.empty()) {
      AddError(result, "self_image:path_failed");
    } else {
      result.self_image = ObserveFile(image, result, "self_image");
    }
    if (production_binary) {
      ObserveBootstrapResource(GetModuleHandleW(nullptr), result);
    } else {
      const std::wstring service_image = SiblingServicePath(image);
      if (service_image.empty()) {
        AddError(result, "service_candidate_image:sibling_path_failed");
      } else {
        result.production_service_image_candidate =
            ObserveFile(service_image, result, "service_candidate_image");
        UniqueModule resource_module(LoadLibraryExW(
            service_image.c_str(), nullptr,
            LOAD_LIBRARY_AS_DATAFILE_EXCLUSIVE |
                LOAD_LIBRARY_AS_IMAGE_RESOURCE));
        if (resource_module.get() == nullptr) {
          AddError(result, "resource:service_candidate_datafile_load_failed");
        } else {
          ObserveBootstrapResource(resource_module.get(), result);
        }
      }
    }
    ObserveLoadedCryptoModules(result);
    ObserveWldp(result);
    ObserveFixedService(result);
    LARGE_INTEGER qpc_end{};
    FILETIME creation_end{}, exit_end{}, kernel_end{}, user_end{};
    const bool interval_end_ok =
        QueryPerformanceCounter(&qpc_end) &&
        GetProcessTimes(GetCurrentProcess(), &creation_end, &exit_end,
                        &kernel_end, &user_end);
    result.qpc_end = qpc_end.QuadPart;
    result.process_creation_time_stable =
        interval_start_ok && interval_end_ok &&
        creation_start.dwHighDateTime == creation_end.dwHighDateTime &&
        creation_start.dwLowDateTime == creation_end.dwLowDateTime;
    result.bounded_qpc_interval_observed =
        interval_start_ok && interval_end_ok && result.qpc_frequency > 0 &&
        result.qpc_start >= 0 && result.qpc_end >= result.qpc_start;
    result.observation_completed = true;
  } catch (const std::exception&) {
    AddError(result, "observer:std_exception_normalized");
  } catch (...) {
    AddError(result, "observer:unknown_exception_normalized");
  }

  if (!result.current_process_token_observed ||
      !result.token_user_is_local_system || !result.service_sid_enabled ||
      !result.service_sid_restricted || !result.token_primary ||
      !result.token_system_integrity || !result.token_linked_absent) {
    result.blockers.emplace_back("SERVICE_PROCESS_TOKEN_NOT_VERIFIED");
  }
  if (!result.self_image.observed) {
    result.blockers.emplace_back("SERVICE_IMAGE_IDENTITY_NOT_VERIFIED");
  }
  if (!production_binary &&
      !result.production_service_image_candidate.observed) {
    result.blockers.emplace_back("SERVICE_CANDIDATE_IMAGE_NOT_OBSERVED");
  }
  if (!result.bootstrap_resource_exact) {
    result.blockers.emplace_back("EMBEDDED_BOOTSTRAP_RESOURCE_NOT_VERIFIED");
  }
  const bool modules_ok = result.modules.size() == 2 &&
      std::all_of(result.modules.begin(), result.modules.end(),
                  [](const ModuleObservation& item) {
                    return item.loaded && item.system32_path &&
                           item.file.observed;
                  });
  if (!modules_ok) {
    result.blockers.emplace_back("LOADED_CNG_PROVIDER_NOT_VERIFIED");
  }
  if (!result.wldp_query_succeeded || !result.wdac_umci_enforced) {
    result.blockers.emplace_back("WDAC_UMCI_NOT_VERIFIED");
  }
  result.blockers.emplace_back("ACTIVE_WDAC_POLICY_IDENTITY_NOT_VERIFIED");
  if (!result.service_present || !result.service_running ||
      !result.service_shape_candidate_config_matches ||
      (production_binary && !result.service_process_is_self)) {
    result.blockers.emplace_back("EXTERNAL_SERVICE_PROVISIONING_NOT_VERIFIED");
  }
  result.blockers.emplace_back("AUTHENTICODE_NOT_VERIFIED");
  result.blockers.emplace_back("EXTERNAL_OWNER_KEY_NOT_VERIFIED");
  result.blockers.emplace_back("TRUSTED_TIME_REVOCATION_NOT_VERIFIED");
  result.blockers.emplace_back("DURABLE_NONCE_NOT_VERIFIED");
  result.blockers.emplace_back("SIGNED_NATIVE_OBSERVER_NOT_VERIFIED");
  return result;
}

CandidateObservation ObserveDiagnosticCandidate() noexcept {
  return ObserveBoundedCandidateInternal(false);
}

CandidateObservation ObserveServiceCandidate() noexcept {
  return ObserveBoundedCandidateInternal(true);
}

std::string DiagnosticJson(const CandidateObservation& value) {
  std::ostringstream out;
  out << "{\"schema_version\":\"p0_windows_owner_observer_diagnostic_v1\""
      << ",\"gate_status\":\"BOUNDED_NATIVE_OBSERVER_CANDIDATE_NO_GO\""
      << ",\"decision\":\"NO_GO\""
      << ",\"operational_effect\":\"NONE_READ_ONLY_DIAGNOSTIC\""
      << ",\"production_binary\":" << JsonBool(value.production_binary)
      << ",\"candidate_only\":" << JsonBool(value.candidate_only)
      << ",\"observation_completed\":"
      << JsonBool(value.observation_completed)
      << ",\"process_id\":" << value.process_id
      << ",\"process_creation_time_100ns\":\""
      << value.process_creation_time_100ns << "\""
      << ",\"process_creation_time_stable\":"
      << JsonBool(value.process_creation_time_stable)
      << ",\"qpc_start\":\"" << value.qpc_start << "\""
      << ",\"qpc_end\":\"" << value.qpc_end << "\""
      << ",\"qpc_frequency\":\"" << value.qpc_frequency << "\""
      << ",\"bounded_qpc_interval_observed\":"
      << JsonBool(value.bounded_qpc_interval_observed)
      << ",\"current_process_token_observed\":"
      << JsonBool(value.current_process_token_observed)
      << ",\"token_user_sid\":\""
      << JsonEscape(WideToUtf8(value.token_user_sid)) << "\""
      << ",\"token_user_is_local_system\":"
      << JsonBool(value.token_user_is_local_system)
      << ",\"service_sid_enabled\":" << JsonBool(value.service_sid_enabled)
      << ",\"service_sid_restricted\":"
      << JsonBool(value.service_sid_restricted)
      << ",\"token_primary\":" << JsonBool(value.token_primary)
      << ",\"token_system_integrity\":"
      << JsonBool(value.token_system_integrity)
      << ",\"token_linked_absent\":"
      << JsonBool(value.token_linked_absent)
      << ",\"self_image\":";
  AppendFileJson(out, value.self_image);
  out << ",\"production_service_image_candidate\":";
  AppendFileJson(out, value.production_service_image_candidate);
  out << ",\"bootstrap_resource_exact\":"
      << JsonBool(value.bootstrap_resource_exact)
      << ",\"bootstrap_resource_sha256\":\""
      << value.bootstrap_resource_sha256 << "\",\"loaded_modules\":[";
  for (std::size_t index = 0; index < value.modules.size(); ++index) {
    if (index != 0) out << ',';
    const ModuleObservation& module = value.modules[index];
    out << "{\"role\":\"" << JsonEscape(module.role)
        << "\",\"expected_name\":\""
        << JsonEscape(WideToUtf8(module.expected_name))
        << "\",\"loaded\":" << JsonBool(module.loaded)
        << ",\"system32_path\":" << JsonBool(module.system32_path)
        << ",\"file\":";
    AppendFileJson(out, module.file);
    out << '}';
  }
  out << "]"
      << ",\"wldp_query_succeeded\":"
      << JsonBool(value.wldp_query_succeeded)
      << ",\"wldp_lockdown_state\":" << value.wldp_lockdown_state
      << ",\"wldp_windows_lockdown_mode\":"
      << value.wldp_windows_lockdown_mode
      << ",\"wdac_umci_enforced\":" << JsonBool(value.wdac_umci_enforced)
      << ",\"active_wdac_policy_identity_verified\":"
      << JsonBool(value.active_wdac_policy_identity_verified)
      << ",\"service_present\":" << JsonBool(value.service_present)
      << ",\"service_running\":" << JsonBool(value.service_running)
      << ",\"service_shape_candidate_config_matches\":"
      << JsonBool(value.service_shape_candidate_config_matches)
      << ",\"service_process_is_self\":"
      << JsonBool(value.service_process_is_self)
      << ",\"service_pid\":" << value.service_pid
      << ",\"external_owner_key_verified\":"
      << JsonBool(value.external_owner_key_verified)
      << ",\"observer_receipt_signature_verified\":"
      << JsonBool(value.observer_receipt_signature_verified)
      << ",\"trusted_time_verified\":"
      << JsonBool(value.trusted_time_verified)
      << ",\"revocation_current_verified\":"
      << JsonBool(value.revocation_current_verified)
      << ",\"durable_nonce_verified\":"
      << JsonBool(value.durable_nonce_verified)
      << ",\"owner_authority_verified\":"
      << JsonBool(value.owner_authority_verified)
      << ",\"actual_authority_granted\":"
      << JsonBool(value.actual_authority_granted)
      << ",\"production_approval\":" << JsonBool(value.production_approval)
      << ",\"full_scan_approval\":" << JsonBool(value.full_scan_approval)
      << ",\"p0_phase_exit\":" << JsonBool(value.p0_phase_exit)
      << ",\"action_applied\":" << JsonBool(value.action_applied)
      << ",\"actual_source_claim_credited_count\":0"
      << ",\"actual_a_context_credited_count\":0"
      << ",\"serialized_receipt_authoritative\":false"
      << ",\"receipt_signed\":false"
      << ",\"loaded_mapping_disk_cross_binding_verified\":false"
      << ",\"trusted_loaded_code_closure_verified\":false"
      << ",\"wdac_policy_identity_hash_verified\":false"
      << ",\"single_interval_store_host_cross_binding_verified\":false"
      << ",\"unnamed_stream_exactness_verified\":false"
      << ",\"blocker_codes\":[";
  for (std::size_t index = 0; index < value.blockers.size(); ++index) {
    if (index != 0) out << ',';
    out << '\"' << JsonEscape(value.blockers[index]) << '\"';
  }
  out << "],\"diagnostic_errors\":[";
  for (std::size_t index = 0; index < value.diagnostic_errors.size(); ++index) {
    if (index != 0) out << ',';
    out << '\"' << JsonEscape(value.diagnostic_errors[index]) << '\"';
  }
  out << "]}";
  return out.str();
}

}  // namespace p0::owner_observer
