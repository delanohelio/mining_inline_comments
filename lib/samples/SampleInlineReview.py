import glob
import pandas as pd
import file_json_utils as json_util
import json


def dataframe_from_json(json_list, record_path=None, meta=None):
    json_to_dataframe = lambda json_data: pd.json_normalize(json_data, record_path=record_path, meta=meta)
    return pd.concat(map(json_to_dataframe, json_list), ignore_index=True)


def dataframe_from_json_file(json_files_list, record_path=None, meta=None):
    file_to_json = lambda file: json.load(open(file))
    json_list = map(file_to_json, json_files_list)
    return dataframe_from_json(json_list, record_path=record_path, meta=meta)


def save_sample(sample, output):
    sample_dict = {}
    sample_inlines = json.loads(sample.to_json(orient="records"))
    for row in sample_inlines:
        json_util.insert_path_in_dict(sample_dict, f"{row['repository']}|{row['pr_number']}", row['id'], separator="|")

    json_util.save_json(output, sample_dict)


def sample_all(num_total, path_data, output, random_state=13):
    prs_inline = glob.glob(f"{path_data}/*/*")
    df_prs_inline = dataframe_from_json_file(prs_inline, ["timeline"], ["pr_number"])
    df_prs_inline["repository"] = df_prs_inline["url"].map(lambda url: "/".join(url.split("/")[3:5])).str.lower()

    df_prs_inline_reviews = df_prs_inline[df_prs_inline["type"] == "inlineReview"]

    df_prs_inline_reviews_by_repos = df_prs_inline_reviews.groupby("repository")

    weights = df_prs_inline_reviews_by_repos.size()

    df_prs_inline_reviews["weights"] = df_prs_inline_reviews['repository'].apply(lambda repo: 1/weights[repo])

    df_prs_inline_reviews.loc[df_prs_inline_reviews_by_repos.sample(1, random_state=random_state).index, "weights"] = 1

    sample = df_prs_inline_reviews.sample(num_total, weights='weights', random_state=random_state).reset_index()

    save_sample(sample, output)


def sample_per_repository(num_total, num_per_repo, path_data, output, random_state=13):
    prs_inline = glob.glob(f"{path_data}/*/*")
    df_prs_inline = dataframe_from_json_file(prs_inline, ["timeline"], ["pr_number"])
    df_prs_inline["repository"] = df_prs_inline["url"].map(lambda url: "/".join(url.split("/")[3:5])).str.lower()

    df_prs_inline_reviews = df_prs_inline[df_prs_inline["type"] == "inlineReview"]
    sample = df_prs_inline_reviews.groupby("repository")[["pr_number", "id"]].apply(
        lambda s: s.sample(num_per_repo, random_state=random_state)).sample(num_total,
                                                                            random_state=random_state).reset_index()[
        ["repository", "pr_number", "id"]]

    sample_dict = {}
    sample_inlines = json.loads(sample.to_json(orient="records"))
    for row in sample_inlines:
        json_util.insert_path_in_dict(sample_dict, f"{row['repository']}|{row['pr_number']}", row['id'], separator="|")

    json_util.save_json(output, sample_dict)


def sample_from_list_url_and_ids(ids_urls_list, output):
    sample_dict = {}
    for row in ids_urls_list:
        url_parts = row["url"].split("/")
        repository_name = "/".join(url_parts[3:5])
        pr_number = url_parts[-1].split("#")[0]
        json_util.insert_path_in_dict(sample_dict, f"{repository_name.lower()}|{pr_number}", row['id'], separator="|")
    json_util.save_json(output, sample_dict)


#sample = pd.read_csv("sample-pilot.csv")
#sample_from_list_url_and_ids(sample.to_dict(orient="records"), "sample-pilot.json")

#sample_per_repository(2000, 6, "data/5-prs_after_inline_comments_filtered", "sample1.json")