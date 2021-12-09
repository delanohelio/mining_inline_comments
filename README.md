# Mining Code Inline Comments Script

It is a script to mine inline comments and aggregate data from GitHub.
The script run in steps that need to be started one by one. These are the steps:
1. Fetch repository pull requests information [info-repo]
2. Filter pull requests based on created date and merge status [filter-prs]
3. Fetch details data of pull requests [details-prs]
4. (Optional) Fetch reviews threads of pull requests [review-threads-prs]
5. Extract the necessary data from pull requests and organize them [process-prs]
6. Filter inline comments (default: whether they are on a Java file) [filter-inline]

---
---

### Dependencies
* Python 3.10
* pandas
* requests

You can use pip to install the requirements.

---
---

### Configuration
#### GitHub Token
Use the file config.json to input your GitHub token. It is possible to includes more tha one.
```
 { 
   "github":{
       "tokens": ["ghp_xxxxx", "ghp_xxxx"],
       "graphql": "https://api.github.com/graphql"
   }
 }
```
#### List of repositories
You need to create a file with a list of repositories separated by lines. This file will be necessary in all steps of script.
For example, you can have a file named _repos_ with this content:
```
antennapod/antennapod
anuken/mindustry
apache/accumulo
apache/activemq-artemis
apache/beam
```
---
---
### Running
The interface to running all steps is the file _run_miner.py_. You will execute a command similar to every step:
```
python run_miner.py [step] -r [repos_file] -i [input_data_path] -o [output_data_path] -t [num_threads] 
```
---
#### info-repo
In this step the script will to fetch basic information about all pull request of repositories. 
The input is a file with the repositories from SEART and the output is a set of files (one by page of the repository).

This step use the file [fetch_repository_prs_info.query](queries/fetch_repository_prs_info.query) as query template to fetch data from GitHub GraphQL API.

**Examples:**

Input file: [SEART_results.json](SEART_results.json)

One of output files: [apache_beam_F2020-02-29T2020-05-02.json](data/1-prs_by_repo/apache_beam_F2020-02-29T2020-05-02.json)

Running (notice that here you do not need the repos file):
```
python run_miner.py info-repo -i SEART_results.json  -o data/1-prs_by_repo -t 5
```
---
#### filter-prs
In this step the script will to filter the pull requests based on the period that the pull request was created and if it was merged.
The input is a path with the data after run the step [info-repos](#info-repos) and the output is a set of files (one by repository).

The parameters to filter are passed in the script using the flags:
* --start_date YYYY-MM-DD 
* --end_date YYYY-MM-DD
* (Optional) --merged [True, False]

**Examples:**

Repos file: [repos](repos)

Input path: [data/1-prs_by_repo](data/1-prs_by_repo)

One of output files: [apache_beam.json](data/2-prs_filtered/apache_beam.json)

```
python run_miner.py filter-prs -r repos -i data/1-prs_by_repo  -o data/2-prs_filtered --start_date 2020-01-01 --end_date 2020-12-31 --merged True -t 5
```
---
#### details-prs
In this step the script will to fetch the detailed data from each pull request of the repositories.
The input is a path with the data after run the step [filter-prs](#filter-prs) and the output is a set of directories (one by repository) with a set of files (one by pull request).

This step use the file [fetch_prs_data_by_pr.query](queries/fetch_prs_data_by_pr.query) as query template to fetch data from GitHub GraphQL API.

**Examples:**

Repos file: [repos](repos)

Input path: [data/2-prs_filtered](data/2-prs_filtered)

One of output files: [apache_beam/pr_10489.json](data/3-details_prs/apache_beam/pr_10489.json)

```
python run_miner.py details-prs -r repos -i data/2-prs_filtered  -o data/3-details_prs -t 5
```
---
#### (optional) review-threads-prs
**You need to run this step if you are interested on the replies of the inline comments.** The query used on [details-prs](#details-prs) step does not return all replies of the inline comments.
The output path need to be the same of the details-prs.

In this step the script will to fetch the head comment and replies of inline comments from each pull request of the repositories.
The input is a path with the data after run the step [filter-prs](#filter-prs) and the output is a set of directories (one by repository) with a set of files (one by pull request).

This step use the file [fetch_review_threads_by_pr.query](queries/fetch_review_threads_by_pr.query) as query template to fetch data from GitHub GraphQL API.

**Examples:**

Repos file: [repos](repos)

Input path: [data/2-prs_filtered](data/2-prs_filtered)

One of output files: [apache_beam/review_thread_pr_10489.json](data/3-details_prs/apache_beam/review_thread_pr_10489.json)

```
python run_miner.py details-prs -r repos -i data/2-prs_filtered  -o data/3-details_prs -t 5
```
---
#### process-prs
In this step the script will to extract and organize the pull request data.
It will extract the inline comments (and their replies if available), commits, and forcePush.
The input is a path with the data after run the step [details-prs](#details-prs) (with [review-threads-prs](#optional-review-threads-prs)) and the output is a set of directories (one by repository) with a set of files (one by pull request).

**Examples:**

Repos file: [repos](repos)

Input path: [data/3-details-prs](data/3-details_prs)

One of output files: [apache_beam/pr_10489.json](data/4-processed_prs/apache_beam/pr_10489.json)

```
python run_miner.py process-prs -r repos -i data/3-details-prs  -o data/4-processed_prs -t 5
```
---
#### filter-inline
In this step the script will to filter the inline comments based on its data. This step can be used to remove inline comments that are not in Java files, for example.
The input is a path with the data after run the step [process-prs](#process-prs) and the output is a set of directories (one by repository) with a set of files (one by pull request).

The filter is processed by the function named _evaluate_acceptable_timeline_item_ in the file [run_miner.py](run_miner.py). You can customize this function to filter by the data that you wish. It is possible to filter commits as well.

**Examples:**

Repos file: [repos](repos)

Input path: [data/4-processed_prs](data/4-processed_prs)

One of output files: [apache_beam/pr_12157.json](data/5-prs_after_inline_comments_filtered/apache_beam/pr_12157.json)

```
python run_miner.py filter-inline -r repos -i data/4-processed-prs  -o data/5-prs_after_inline_comments_filtered -t 5
```
---

#### Example of a complete running
```
python run_miner.py info-repo -i SEART_results.json  -o data/1-prs_by_repo -t 5
python run_miner.py filter-prs -r repos -i data/1-prs_by_repo  -o data/2-prs_filtered --start_date 2020-01-01 --end_date 2020-12-31 --merged True -t 5
python run_miner.py details-prs -r repos -i data/2-prs_filtered  -o data/3-details_prs -t 5
python run_miner.py details-prs -r repos -i data/2-prs_filtered  -o data/3-details_prs -t 5
python run_miner.py process-prs -r repos -i data/3-details-prs  -o data/4-processed_prs -t 5
python run_miner.py filter-inline -r repos -i data/4-processed-prs  -o data/5-prs_adter_inline_comments_filtered -t 5
```
---

#### Tips
* In the steps where the script will fetch data from GitHub, sometimes it will need to start more tha once the same step because you can reach the limit of access. In this case, you need to wait a time to start the same step again, the script will to skip the data fetched.
---

#### Extra
* This script can to extract the changes after the inline comments, but it still is on development.
* This script has a code to extract sample of the data, but it is not available on the interface.
* There is a page (html) that can show the fetched data (after process-prs step) summarized, but it still is on development.
