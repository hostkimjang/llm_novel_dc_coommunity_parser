#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace p0::owner_observer {

inline constexpr wchar_t kServiceName[] =
    L"llm-novel-dc-p0-owner-verifier-v2";
inline constexpr wchar_t kExpectedServiceSid[] =
    L"S-1-5-80-1513470239-1791686718-1237107998-66343029-3355175470";
inline constexpr wchar_t kBootstrapResourceType[] =
    L"P0_OWNER_BOOTSTRAP_V2";
inline constexpr wchar_t kBootstrapResourceName[] =
    L"OWNER_POLICY_P256_SPKI";

struct FileObservation {
  bool observed{false};
  bool no_reparse{false};
  bool single_link{false};
  bool identity_stable{false};
  std::wstring path;
  std::wstring final_volume_guid_path;
  std::uint64_t volume_serial{0};
  std::string file_id_128_hex;
  std::string sha256;
};

struct ModuleObservation {
  std::string role;
  std::wstring expected_name;
  bool loaded{false};
  bool system32_path{false};
  FileObservation file;
};

struct CandidateObservation {
  bool production_binary{false};
  bool candidate_only{true};
  bool observation_completed{false};
  std::uint32_t process_id{0};
  std::uint64_t process_creation_time_100ns{0};
  bool process_creation_time_stable{false};
  std::int64_t qpc_start{0};
  std::int64_t qpc_end{0};
  std::int64_t qpc_frequency{0};
  bool bounded_qpc_interval_observed{false};
  bool current_process_token_observed{false};
  bool token_user_is_local_system{false};
  bool service_sid_enabled{false};
  bool service_sid_restricted{false};
  bool token_primary{false};
  bool token_system_integrity{false};
  bool token_linked_absent{false};
  std::wstring token_user_sid;
  FileObservation self_image;
  FileObservation production_service_image_candidate;
  bool bootstrap_resource_exact{false};
  std::string bootstrap_resource_sha256;
  std::vector<ModuleObservation> modules;
  bool wldp_query_succeeded{false};
  std::uint32_t wldp_lockdown_state{0};
  std::int32_t wldp_windows_lockdown_mode{-1};
  bool wdac_umci_enforced{false};
  bool active_wdac_policy_identity_verified{false};
  bool service_present{false};
  bool service_running{false};
  bool service_shape_candidate_config_matches{false};
  bool service_process_is_self{false};
  std::uint32_t service_pid{0};
  bool external_owner_key_verified{false};
  bool observer_receipt_signature_verified{false};
  bool trusted_time_verified{false};
  bool revocation_current_verified{false};
  bool durable_nonce_verified{false};
  bool owner_authority_verified{false};
  bool actual_authority_granted{false};
  bool production_approval{false};
  bool full_scan_approval{false};
  bool p0_phase_exit{false};
  bool action_applied{false};
  std::vector<std::string> blockers;
  std::vector<std::string> diagnostic_errors;
};

CandidateObservation ObserveDiagnosticCandidate() noexcept;
CandidateObservation ObserveServiceCandidate() noexcept;
std::string DiagnosticJson(const CandidateObservation& observation);

}  // namespace p0::owner_observer
