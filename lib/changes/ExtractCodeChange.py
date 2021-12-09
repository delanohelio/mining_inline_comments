import re
import os
import subprocess
from datetime import datetime


def extract_lines_in_chunk(diff):
    diff_header = diff.split("@@")[1]
    base_chunk, new_chunk = diff_header.split()
    diff_lines = diff.split("\n")[1:]

    base_chunk = re.findall(r'\d+', base_chunk)
    base_chunk = [int(i) for i in base_chunk]
    base_size = len(list(filter(lambda line: not line.startswith("+"), diff_lines)))

    new_chunk = re.findall(r'\d+', new_chunk)
    new_chunk = [int(i) for i in new_chunk]
    new_size = len(list(filter(lambda line: not line.startswith("-"), diff_lines)))

    # scenario: @@ -1 +1 @@
    if len(base_chunk) < 2:
        base_chunk.append(0)

    if len(new_chunk) < 2:
        new_chunk.append(0)

    return {"base": {
        "start": base_chunk[0],
        "end": base_chunk[0] + base_chunk[1],
        "size": base_size
    },
        "new": {
            "start": new_chunk[0],
            "end": new_chunk[0] + new_chunk[1],
            "size": new_size
        }
    }


def extract_files_chunks(diff_file):
    all_chunks = {}
    current_file = ""
    file_header = ""
    file_chunks = []
    current_chunk = ""
    current_chunk_contains_changes = False

    for line in diff_file:
        if line.startswith("diff --git"):
            if current_file != "" and current_chunk_contains_changes:
                file_chunks.append(current_chunk)
                all_chunks[current_file] = {"header": file_header, "chunks": file_chunks}
            current_file = line.split()[2][2:]
            file_header = line
            current_chunk = ""
            current_chunk_contains_changes = False
        elif line.startswith("+++ b/") or line.startswith("+++ /dev/null"):
            file_header = file_header + current_chunk + line
            file_chunks = []
            current_chunk = ""
            current_chunk_contains_changes = False
        elif line.startswith("@@"):
            if current_chunk != "":
                file_chunks.append(current_chunk)
            current_chunk = line
            current_chunk_contains_changes = True
        else:
            current_chunk = current_chunk + line

    if current_chunk_contains_changes:
        file_chunks.append(current_chunk)
        all_chunks[current_file] = {"header": file_header, "chunks": file_chunks}

    return all_chunks


def get_diff(repository_name, repository_path, base_commit_sha, new_commit_sha, diffs_path="tmp/diffs"):
    diff_file_path = f"{diffs_path}/{repository_name.replace('/', '_')}/{base_commit_sha}..{new_commit_sha}.diff"
    if not os.path.isfile(diff_file_path):
        diff_command = subprocess.run(["git", "diff", base_commit_sha, new_commit_sha, "--", "*.java"],
                                      cwd=repository_path,
                                      capture_output=True)

        if diff_command.returncode == 0:
            diff_result = diff_command.stdout
        else:
            fetch_command = subprocess.run(["git", "fetch", "origin", base_commit_sha, new_commit_sha],
                                           cwd=repository_path,
                                           capture_output=True, universal_newlines=True, check=False)
            if fetch_command.returncode == 0:
                diff_command = subprocess.run(["git", "diff", base_commit_sha, new_commit_sha, "--", "*.java"],
                                              cwd=repository_path,
                                              capture_output=True, check=True)
                diff_result = diff_command.stdout
                if diff_result == b'':
                    print(f"Diff of {base_commit_sha} and {new_commit_sha} of repo {repository_name} is blank")
            else:
                print(f"Fetch of {base_commit_sha} and {new_commit_sha} of repo {repository_name} not work well")
                diff_result = b''
        os.makedirs(os.path.dirname(diff_file_path), exist_ok=True)
        with open(diff_file_path, 'w') as file:
            file.write(diff_result.decode("utf-8", "ignore"))
            file.flush()

    with open(diff_file_path, 'r') as file:
        lines = file.readlines()
        file.flush()

    return lines


def search_changed_chunk(file_path, diff_hunk, commits_diff):
    chunks = extract_files_chunks(commits_diff)

    header_chunk_review = extract_lines_in_chunk(diff_hunk)
    #header_chunk_review_start_line = header_chunk_review["new"]["start"]
    #header_chunk_review_end_line = header_chunk_review["new"]["end"]
    header_chunk_review_end_line = header_chunk_review["new"]["start"] + header_chunk_review["new"]["size"]
    header_chunk_review_start_line = header_chunk_review_end_line - 4
    if header_chunk_review_start_line < 0:
        header_chunk_review_start_line = 0
    header_chunk_review_range = header_chunk_review_end_line - header_chunk_review_start_line + 1

    if file_path in chunks:
        list_chunks_in_file = chunks[file_path]["chunks"]

        for chunk in list_chunks_in_file:
            candidate_revised_header_chunk = extract_lines_in_chunk(chunk)

            candidate_revised_chunk_start_line = candidate_revised_header_chunk["base"]["start"]
            candidate_revised_chunk_end_line = candidate_revised_header_chunk["base"]["end"]
            candidate_revised_chunk_range = candidate_revised_chunk_end_line - candidate_revised_chunk_start_line + 1

            range_min = min(header_chunk_review_start_line, candidate_revised_chunk_start_line)
            range_max = max(header_chunk_review_end_line, candidate_revised_chunk_end_line)

            total_range = range_max - range_min
            total_width = header_chunk_review_range + candidate_revised_chunk_range

            if total_range < total_width:
                yield {"header": chunks[file_path]['header'],
                       "chunk": chunk}

    return None


def get_revised_chunk(diff_hunk, file_path, original_commit, next_commits, repository_name, cloned_repository_path):
    for index, oid_commit in enumerate(next_commits):
        diff = get_diff(repository_name, cloned_repository_path, original_commit, oid_commit)
        found_changed_chunks = list(search_changed_chunk(file_path, diff_hunk, diff))

        if found_changed_chunks:
            for changed_chunk in found_changed_chunks:
                changed_chunk_diff = changed_chunk["chunk"]
                changed_chunk_commit = oid_commit
                changed_chunk_next_commits = next_commits[index + 1:]
                changed_chunk["next_change"] = get_revised_chunk(changed_chunk_diff, file_path, changed_chunk_commit,
                                                                 changed_chunk_next_commits, repository_name,
                                                                 cloned_repository_path)

            return {"commit": changed_chunk_commit,
                    "changed_code": found_changed_chunks}

    return None


def search_revised_code_in_pr(pull_request, repository_name, cloned_repository_path):
    pr_timeline = pull_request["timeline"]

    template_time = "%Y-%m-%dT%H:%M:%SZ"
    commits = list(filter(lambda item: item["type"] in ["commit", "forcePushed"], pr_timeline))
    inline_review_list = list(filter(lambda item: item["type"] == "inlineReview", pr_timeline))

    revised_chunk_inline_reviews = {}

    for inline_review in inline_review_list:
        original_oid_inline_review = inline_review["originalCommit"]
        inline_review_created_at = datetime.strptime(inline_review["createdAt"], template_time)
        next_commits = list(filter(
            lambda commit: inline_review_created_at < datetime.strptime(commit["committedDate"], template_time),
            commits))
        next_commits = list(map(lambda commit: commit["oid"], next_commits))

        file_path = inline_review["path"]
        diff_hunk = inline_review["diffHunk"]

        revised_chunk_inline_reviews[inline_review["id"]] = get_revised_chunk(diff_hunk, file_path,
                                                                              original_oid_inline_review, next_commits,
                                                                              repository_name, cloned_repository_path)

    return revised_chunk_inline_reviews


def clone_repository(repository_name, cloned_path, overwrite=False):
    repository_output_path = f"{cloned_path}/{repository_name.replace('/', '_')}"
    if overwrite or not os.path.isdir(repository_output_path):
        subprocess.run(["git", "clone", f"https://github.com/{repository_name}.git", repository_output_path],
                       capture_output=True, universal_newlines=True, check=True)
    return repository_output_path
