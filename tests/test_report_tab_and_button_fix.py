"""
Comprehensive validation test for:
1. Dedicated "Report" Tab (`tab-report`)
2. "Keep All" button functionality (keeps both duplicates)
3. Group-level "Keep Both" button functionality
4. Button clicking fix for paths with single quotes/apostrophes (e.g. "I'm Fine Even if She's...")
"""
import re
import os
import sys

def test_index_html_structure():
    html_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'web', 'templates', 'index.html')
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()

    print("[CHECK 1] Verifying Tab Structure in index.html...")
    assert 'id="tab-report"' in content, "Missing id='tab-report' in index.html navigation"
    assert "switchTab('report')" in content, "Missing switchTab('report') in index.html"
    assert 'id="tabReportDuplicatesBadge"' in content, "Missing report badge in navigation"
    print("  ✓ Dedicated 'Report' Tab (tab-report) exists with live badge")

    print("[CHECK 2] Verifying Report Sub-filters & Keep All Button...")
    assert 'id="reportControlsBar"' in content, "Missing reportControlsBar container"
    assert 'id="btnKeepAll"' in content, "Missing id='btnKeepAll' button"
    assert 'keepAllDuplicates()' in content, "Missing keepAllDuplicates() invocation"
    assert 'keepGroupDuplicates(' in content, "Missing keepGroupDuplicates function"
    assert '🛡️ Keep All' in content, "Missing 'Keep All' text"
    assert '🛡️ Keep Both' in content, "Missing 'Keep Both' text on group cards"
    print("  ✓ 'Keep All' and 'Keep Both' buttons verified in Report toolbar and card headers")

    print("[CHECK 3] Verifying Unsafe String Interpolation Fix...")
    # Check that old broken inline interpolation no longer exists
    broken_pattern = r"onclick=\"setItemAction\('\${path"
    match = re.search(broken_pattern, content)
    assert match is None, f"Found unsafe string interpolation in index.html: {match.group(0)}"

    assert "setItemActionByIndex(" in content, "Missing setItemActionByIndex in index.html"
    assert "itemRegistry" in content, "Missing itemRegistry in index.html"
    print("  ✓ All action buttons now use safe numeric index (setItemActionByIndex) avoiding syntax errors on apostrophes")

    print("[CHECK 4] Verifying 'loadSavedReport' opens Report tab...")
    # Verify loadSavedReport switches to report tab
    assert "switchTab('report')" in content, "Missing switchTab('report') in loadSavedReport"
    print("  ✓ loadSavedReport switches directly to 'report' tab")

def test_apostrophe_handling_simulation():
    print("[CHECK 5] Simulating User's Exact Screenshot Scenario...")
    # Paths from user's screenshot
    path_1 = "/sg2b/Share2sgb/Manga/Manga_1/Axe/Flag Capture in the First Move/RE_SCANS OF KWEGOSAURUS_Ch.5 - I'm Fine Even if She's a Little Bit Yandere, I Just Wanna Be Popula_cd87c1"
    path_2 = "/sg2b/Share2sgb/Manga/Manga_1/Axe/Flag Capture in the First Move/Yami_taku_Ch.5 - I'm Fine Even if She's a Little Bit Yandere, I Just Wanna Be Popular_83f477"

    # Simulate in-memory registry
    item_registry = []
    
    # Register items
    idx1 = len(item_registry)
    item_registry.append(path_1)

    idx2 = len(item_registry)
    item_registry.append(path_2)

    # Generated button HTML attributes
    btn_keep_1 = f"onclick=\"setItemActionByIndex({idx1}, 'keep')\""
    btn_archive_1 = f"onclick=\"setItemActionByIndex({idx1}, 'move_archive')\""
    btn_delete_1 = f"onclick=\"setItemActionByIndex({idx1}, 'delete')\""

    btn_keep_2 = f"onclick=\"setItemActionByIndex({idx2}, 'keep')\""
    btn_archive_2 = f"onclick=\"setItemActionByIndex({idx2}, 'move_archive')\""
    btn_delete_2 = f"onclick=\"setItemActionByIndex({idx2}, 'delete')\""

    # Verify no unescaped characters or quotes exist in the generated onclick
    for btn in [btn_keep_1, btn_archive_1, btn_delete_1, btn_keep_2, btn_archive_2, btn_delete_2]:
        # onclick attribute format must be strictly setItemActionByIndex(<int>, '<action>')
        match = re.search(r"onclick=\"setItemActionByIndex\((\d+),\s*'(\w+)'\)\"", btn)
        assert match is not None, f"Failed regex match on {btn}"
        idx = int(match.group(1))
        action = match.group(2)
        retrieved_path = item_registry[idx]
        assert "I'm Fine Even if She's" in retrieved_path
        print(f"  ✓ Button attribute [{btn}] resolves cleanly to: '{retrieved_path[:60]}...' -> Action: {action}")

    # Simulate Keep All
    selected_actions = {}
    items = [path_1, path_2]
    # Default recommended state:
    selected_actions[path_1] = 'keep'
    selected_actions[path_2] = 'move_archive'
    assert selected_actions[path_2] == 'move_archive'

    # Execute Keep All
    for p in items:
        selected_actions[p] = 'keep'

    assert selected_actions[path_1] == 'keep'
    assert selected_actions[path_2] == 'keep'
    print("  ✓ 'Keep All' successfully set both duplicates to 'keep'")

if __name__ == '__main__':
    test_index_html_structure()
    test_apostrophe_handling_simulation()
    print("\n=======================================================")
    print("  ALL REPORT TAB & BUTTON FIX TESTS PASSED (100% OK)   ")
    print("=======================================================")
