"""
Unified Patch Engine for RAMAZAN AI.
Supports applying unified diffs, hunk patches, and search/replace blocks to existing files.
"""

import re
from typing import Tuple


def apply_patch_to_text(original_text: str, patch_str: str) -> Tuple[bool, str, str]:
    """
    Applies unified diff or search/replace block to original text.
    Returns (success: bool, new_text: str, message: str).
    """
    # 1. Search/replace format: <<<<<<< SEARCH ... ======= ... >>>>>>> REPLACE
    if "<<<<<<< SEARCH" in patch_str and "=======" in patch_str and ">>>>>>> REPLACE" in patch_str:
        pattern = r"<<<<<<< SEARCH\s*\n(.*?)\n=======\s*\n(.*?)\n>>>>>>> REPLACE"
        matches = list(re.finditer(pattern, patch_str, re.DOTALL))
        if matches:
            res = original_text
            count = 0
            for m in matches:
                search_block = m.group(1)
                replace_block = m.group(2)
                if search_block in res:
                    res = res.replace(search_block, replace_block, 1)
                    count += 1
                else:
                    # Try whitespace stripped match
                    s_clean = search_block.strip()
                    if s_clean in res:
                        res = res.replace(s_clean, replace_block.strip(), 1)
                        count += 1
                    else:
                        return False, original_text, f"Search block not found in file: {search_block[:80]}..."
            return True, res, f"Applied {count} search/replace blocks."

    # 2. Unified diff hunks (@@ -start,len +start,len @@)
    patch_lines = patch_str.splitlines()
    hunks = []
    current_hunk = None
    for line in patch_lines:
        if line.startswith("@@"):
            if current_hunk:
                hunks.append(current_hunk)
            current_hunk = {"header": line, "lines": []}
        elif current_hunk is not None:
            if not (line.startswith("---") or line.startswith("+++")):
                current_hunk["lines"].append(line)
    if current_hunk:
        hunks.append(current_hunk)

    if not hunks:
        return False, original_text, "No valid unified diff hunks or search/replace blocks found."

    orig_lines = [l.rstrip("\r\n") for l in original_text.splitlines()]

    for hunk in hunks:
        h_lines = hunk["lines"]
        expected = []
        replacement = []
        for hl in h_lines:
            if hl.startswith(" "):
                expected.append(hl[1:])
                replacement.append(hl[1:])
            elif hl.startswith("-"):
                expected.append(hl[1:])
            elif hl.startswith("+"):
                replacement.append(hl[1:])
            elif hl == "":
                expected.append("")
                replacement.append("")

        found_idx = -1
        exp_len = len(expected)
        for i in range(len(orig_lines) - exp_len + 1):
            if orig_lines[i : i + exp_len] == expected:
                found_idx = i
                break

        if found_idx == -1:
            # Fuzzy match (ignoring leading/trailing whitespace)
            exp_stripped = [l.strip() for l in expected]
            for i in range(len(orig_lines) - exp_len + 1):
                if [l.strip() for l in orig_lines[i : i + exp_len]] == exp_stripped:
                    found_idx = i
                    break

        if found_idx == -1:
            return False, original_text, f"Could not find matching context in target file for hunk: {hunk['header']}"

        orig_lines = orig_lines[:found_idx] + replacement + orig_lines[found_idx + exp_len :]

    result_text = "\n".join(orig_lines)
    if original_text.endswith("\n"):
        result_text += "\n"

    return True, result_text, f"Applied {len(hunks)} patch hunks successfully."
