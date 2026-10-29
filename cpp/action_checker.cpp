#include <cstring>

namespace {
bool equals(const char* value, const char* expected) {
    return value != nullptr && std::strcmp(value, expected) == 0;
}

bool valid_kind(const char* kind) {
    return equals(kind, "observe") || equals(kind, "verify_fixture") ||
           equals(kind, "pick") || equals(kind, "install") ||
           equals(kind, "tool_change") || equals(kind, "fasten") ||
           equals(kind, "inspect") || equals(kind, "label") ||
           equals(kind, "transfer") || equals(kind, "wait") ||
           equals(kind, "rework");
}

bool valid_target(const char* target) {
    return equals(target, "cover") || equals(target, "driver") ||
           equals(target, "gripper") || equals(target, "assembly");
}
}  // namespace

extern "C" int vcrisp_checker_abi_version() {
    return 1;
}

extern "C" const char* vcrisp_checker_compiler() {
    return __VERSION__;
}

extern "C" const char* vcrisp_check_action(
    const char* kind,
    const char* target,
    const char* declared_tool,
    const char* complexity,
    const char* current_tool,
    const char* holding,
    int pose_known,
    int fixture_verified,
    int cover_installed,
    int fastened,
    int quality_pass,
    int label_applied,
    int station_blocked,
    int driver_unavailable,
    int rework_required) {
    if (!valid_kind(kind)) return "unknown_operator";
    if (!valid_target(target)) return "unknown_target";
    if (equals(kind, "fasten") &&
        !equals(declared_tool, "driver") && !equals(declared_tool, "gripper")) {
        return "malformed_tool_field";
    }
    if (equals(kind, "label") && declared_tool != nullptr &&
        !equals(declared_tool, "gripper")) {
        return "malformed_tool_field";
    }

    if (equals(kind, "observe") || equals(kind, "verify_fixture") ||
        equals(kind, "wait")) return nullptr;
    if (equals(kind, "tool_change")) {
        if (equals(target, "driver") && driver_unavailable) return "driver_unavailable";
        return nullptr;
    }
    if (equals(kind, "pick")) {
        if (!equals(target, "cover")) return "unknown_target";
        if (!equals(current_tool, "gripper")) return "pick_requires_gripper";
        if (!pose_known) return "pose_unknown";
        if (holding != nullptr) return "robot_not_empty";
        if (cover_installed) return "cover_already_installed";
        return nullptr;
    }
    if (equals(kind, "install")) {
        if (!equals(holding, "cover")) return "cover_not_held";
        if ((equals(complexity, "standard") || equals(complexity, "extended")) &&
            !fixture_verified) return "fixture_not_verified";
        if (station_blocked) return "station_blocked";
        return nullptr;
    }
    if (equals(kind, "fasten")) {
        if (!equals(declared_tool, "driver")) return "tool_incompatible";
        if (!equals(current_tool, "driver")) return "fasten_requires_driver";
        if (!cover_installed) return "cover_not_installed";
        return nullptr;
    }
    if (equals(kind, "inspect")) {
        if (!cover_installed || !fastened) return "inspection_precondition_failed";
        if (rework_required) return "rework_required";
        return nullptr;
    }
    if (equals(kind, "label")) {
        if (!equals(complexity, "extended")) return "label_not_required";
        if ((declared_tool != nullptr && !equals(declared_tool, "gripper")) ||
            !equals(current_tool, "gripper")) return "label_requires_gripper";
        if (!quality_pass) return "quality_not_passed";
        return nullptr;
    }
    if (equals(kind, "transfer")) {
        if (!quality_pass) return "quality_not_passed";
        if (equals(complexity, "extended") && !label_applied) return "label_not_applied";
        return nullptr;
    }
    if (equals(kind, "rework")) {
        if (!rework_required) return "rework_not_authorized";
        return nullptr;
    }
    return "unknown_operator";
}
