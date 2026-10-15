#pragma once
// Grim Dawn types and exported symbol names used by the hook.
//
// ItemReplicaInfo's layout is adapted from GrimDawnItemAssistant
// (HookDll/Hook/GrimTypes.h, MIT License, Copyright (c) 2019 marius00).
// It must match the shipped Game.dll exactly; tooltip_hook.cpp guards against
// the game writing past the end of it after a patch.

#include <string>

namespace gg::game {

struct Vec3 {
    float x;
    float y;
    float z;
};

struct ItemReplicaInfo {
    unsigned int id;
    std::string baseRecord;
    std::string prefixRecord;
    std::string suffixRecord;
    unsigned int seed;
    std::string modifierRecord;
    std::string materiaRecord;
    std::string relicBonus;
    unsigned int relicSeed;
    std::string enchantmentRecord;
    unsigned int enchantmentLevel;
    unsigned int enchantmentSeed;
    std::string transmuteRecord;
    std::string ascendant1;
    std::string ascendant2;
    unsigned int var1;
    Vec3 velocity;
    unsigned int owner;
    unsigned int unknownDropData;
    unsigned int stackSize;
    unsigned int seedRerolls;
    unsigned int affixRerolls;
    unsigned int unknownFoaField1;
    unsigned int unknownFoaField2;
};

// One line of a tooltip as the game builds it (also from IA's GrimTypes.h).
// `text` may still contain colour codes such as {^E}.
struct GameTextLine {
    int textClass;  // GAME::GameTextClass; 0x11 base stats, 0x12 bonuses, ...
    std::wstring text;
    bool needsProcessing;
    void* leadingIcon;
    float iconScale;
};

// mem::vector<T> is laid out as three pointers, like MSVC's std::vector.
struct GameTextLineVector {
    GameTextLine* first;
    GameTextLine* last;
    GameTextLine* end;
};

// Upper bound for a plausible GameTextClass, used only as a sanity check that
// the vector really holds GameTextLines. The enum has grown since IA's copy
// (1.3.1 uses at least 0x42 for the item-type line and shifts IA's values by
// one), so this is deliberately loose.
inline constexpr int kMaxGameTextClass = 0xFF;

#if defined(_MSC_VER) && !defined(__clang__)
static_assert(sizeof(GameTextLine) == 0x40, "unexpected GameTextLine size");
// Retail Grim Dawn 1.3 (Fangs of Asterkarn). Only meaningful for an MSVC build;
// other compilers lay out std::string differently.
static_assert(sizeof(ItemReplicaInfo) == 0x190,
              "ItemReplicaInfo layout does not match retail Grim Dawn 1.3");
#endif

// Exported from Game.dll. Mangled names encode the signature, so a patch that
// changes a signature makes the lookup fail instead of calling the wrong thing.
// Newest signature first.
inline constexpr const char* kItemEquipmentGetUIDisplayText4 =
    "?GetUIDisplayText@ItemEquipment@GAME@@UEBAXPEBVCharacter@2@AEAV?$vector@UGameTextLine@GAME@@@mem@@_N@Z";
inline constexpr const char* kItemEquipmentGetUIDisplayText3 =
    "?GetUIDisplayText@ItemEquipment@GAME@@UEBAXPEBVCharacter@2@AEAV?$vector@UGameTextLine@GAME@@@mem@@@Z";
inline constexpr const char* kItemGetItemReplicaInfo =
    "?GetItemReplicaInfo@Item@GAME@@UEBAXAEAUItemReplicaInfo@2@@Z";

}  // namespace gg::game
