from ..utils import file_json_utils as json_util
import glob
import re
import os


def prs_files_to_csv(list_repositories, prs_extracted_changes_path, output_csv_file_path,
                     selected_prs_by_repo_path=None):
    print(f"It will generate a csv from data in {prs_extracted_changes_path}")
    print(f"The file will save in {output_csv_file_path}")
    print(f"The selected data in {selected_prs_by_repo_path}")

    selected_prs_by_repo = None
    if selected_prs_by_repo_path is not None:
        selected_prs_by_repo = json_util.open_json(selected_prs_by_repo_path)

    output_string = ""
    for repository_name in list_repositories:
        print(f"Processing repository {repository_name}")
        repository_dir_name = repository_name.replace("/", "_")
        if selected_prs_by_repo is not None:
            if repository_name not in selected_prs_by_repo:
                print(f"Repository {repository_name} not found in sample {selected_prs_by_repo_path}")
                continue
            selected_prs = selected_prs_by_repo[repository_name]
            prs_filenames = list(
                map(lambda pr_num: f"{prs_extracted_changes_path}/{repository_dir_name}/pr_{pr_num}.json",
                    selected_prs))
        else:
            prs_filenames = glob.glob(f"{prs_extracted_changes_path}/{repository_dir_name}/*.json")

        prs_string_output = ""
        # prs_string_output += "\n\n"
        # prs_string_output = "PR Number\tPR Title / Timeline Item type\tURL\tCreated At\tOID / Review ID\tMessage\n"

        for pr_filename in prs_filenames:
            pr_data = json_util.open_json(pr_filename)
            pr_number = pr_data["pr_number"]
            # pr_title = pr_data["pr_title"]
            # pr_url = pr_data["pr_url"]
            # pr_created = pr_data["pr_createdAt"]
            # pr_actual_string_output = f"{pr_number}\t{pr_title}\t{pr_url}\t{pr_created}\n"
            pr_actual_string_output = ""

            pr_timeline = pr_data["timeline"]

            if selected_prs_by_repo is not None:
                selected_inline_reviews = json_util.get_path_in_dict(selected_prs_by_repo,
                                                                     f"{repository_name}|{pr_number}", separator="|")
                if selected_inline_reviews is not None:
                    pr_timeline = filter(
                        lambda item: item["type"] == "inlineReview" and item["id"] in selected_inline_reviews,
                        pr_timeline)

            for timeline_item in pr_timeline:

                type_name = timeline_item["type"]

                if type_name == "commit" or type_name == "forcePushed":
                    continue
                    # oid = timeline_item["oid"]
                    # committed_date = timeline_item["committedDate"]
                    # commit_url = timeline_item["url"]
                    # commit_message = re.sub(r"\n|\t|\r", " ", timeline_item["message"])
                    # pr_actual_string_output += f"\t{type_name}\t{commit_url}\t{committed_date}\t{oid}\t{commit_message}\n"

                elif type_name == "inlineReview":
                    comment_create_at = timeline_item["createdAt"]
                    comment_body_text = re.sub(r"\n|\t|\r", " ", timeline_item["bodyText"])
                    comment_url = timeline_item["url"]
                    comment_id = timeline_item["id"]
                    contains_replies = timeline_item["replies"] is not None
                    pr_actual_string_output += f"{repository_name}\t{pr_number}\t{comment_id}\t{comment_body_text}\t{contains_replies}\n"

            prs_string_output += pr_actual_string_output
            #prs_string_output += "\n\n"

        output_string += prs_string_output

    os.makedirs(output_csv_file_path, exist_ok=True)
    with open(f"{output_csv_file_path}/code_reviews.csv", "w") as f:
        f.write(output_string)
