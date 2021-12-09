from ..utils import file_json_utils as json_util
import pandas as pd
import glob
import os
from datetime import datetime


def dataframe_from_json_of_repository(repository_name, input_path):
    repository_name = repository_name.replace("/", "_")
    repository_files = glob.glob(f"{input_path}/{repository_name}.json")
    if len(repository_files) == 0:
        repository_files = glob.glob(f"{input_path}/{repository_name}_*.json")

    items_json_path = ["data", "search", "nodes"]
    json_to_dataframe = lambda file: pd.json_normalize(json_util.open_json(file), record_path=items_json_path)

    return pd.concat(map(json_to_dataframe, repository_files), ignore_index=True)


def extend_data_to_repository_prs(df_prs_info):
    if len(df_prs_info) > 0:
        df_prs_info["createdAt.date"] = df_prs_info["createdAt"].map(
            lambda createdAt: datetime.strptime(createdAt, "%Y-%m-%dT%H:%M:%SZ"))
        df_prs_info["inlineReviews.totalCount"] = df_prs_info["timelineItems.nodes"].map(
            calculate_total_inlines_review_of_pull_request)
    return df_prs_info


def calculate_total_inlines_review_of_pull_request(timelineItems):
    return sum(item["comments"]["totalCount"] for item in timelineItems)


def calculate_total_inlines_review_of_repository(df_repository, filter_by_created_start=None,
                                                 filter_by_created_end=None):
    if len(df_repository) > 0:
        if filter_by_created_start and filter_by_created_end:
            mask = (df_repository["createdAt.date"] >= filter_by_created_start) & (
                    df_repository["createdAt.date"] <= filter_by_created_end)
            df_repository = df_repository.loc[mask]
        return sum(df_repository["inlineReviews.totalCount"])

    else:
        return 0


# When you want to ignore filter use the value None.
# To filter by merged, True means just merged prs, False means just not merged prs, and None means not use this filter.
def select_prs_by_date_and_num_of_inline_reviews_by_repository(repository_name, input_path, output_path,
                                                               num_min_inline=1,
                                                               filter_by_merged_status=None,
                                                               filter_by_created_start=None,
                                                               filter_by_created_end=None,
                                                               overwrite=False):

    output_file_path = f"{output_path}/{repository_name.replace('/', '_')}.json"
    print(f"Filtering pull request of {repository_name}")

    if overwrite or not os.path.isfile(output_file_path):
        repository_df = dataframe_from_json_of_repository(repository_name, input_path)
        repository_df = extend_data_to_repository_prs(repository_df)
        repository_df["repository"] = repository_name

        df_filtered = repository_df[
            ["repository", "id", "number", "merged", "createdAt.date", "inlineReviews.totalCount"]]

        mask = df_filtered["inlineReviews.totalCount"] >= num_min_inline
        if filter_by_merged_status:
            mask = mask & (df_filtered["merged"] == filter_by_merged_status)
        if filter_by_created_start:
            mask = mask & (df_filtered["createdAt.date"] >= filter_by_created_start)
        if filter_by_created_end:
            mask = mask & (df_filtered["createdAt.date"] <= filter_by_created_end)

        df_filtered = df_filtered.loc[mask]

        os.makedirs("/".join(output_file_path.split("/")[:-1]), exist_ok=True)
        df_filtered.to_json(output_file_path, orient="records")
        print(f"File with filtered pull requests of {repository_name} saved in {output_file_path}")
    else:
        print(f"Skipped repository {repository_name}")
