import os
import pandas as pd
import google.generativeai as genai
import warnings
import time
import tabulate

warnings.filterwarnings("ignore", category=UserWarning)

### TO_DO: if no students started the assignment, then have separate sentence.
### TO_DO: to use the examples that teachers liked into the few shot examples.



# Read the API key from a file
api_key_file = '/Users/ivanlim/Documents/GitHub/GoogleAIStudioAPIKey.txt'  # Define the path to your API key file
with open(api_key_file, 'r') as f:
    api_key = f.read().strip()

# Configure the API key
genai.configure(api_key=api_key)

# Read Excel files into dataframes
data_folder = 'data/random'

# Add download timestamp of file
timestamp = "20250220"  # Replace with timestamp

# Define the files with the base names
files_basename = {
    'a1_assignment_details.xlsx': 'assignment_details',
    'a3_problem_details.xlsx': 'problem_details',
    'a2_student_details.xlsx': 'student_details',
    'a4_student_problem_details.xlsx': 'student_problem_details'
}

# Export the results to an Excel file
output_file = './data/output/aggre/assignment_summaries.xlsx'
output_text = './data/output/aggre/assignment_detailed_text.xlsx'
token_file = './data/output/aggre/token_count.xlsx'

# Create a new dictionary with updated filenames including the timestamp
files = {
    f"{file_name.replace('.xlsx', '')}_{timestamp}.xlsx": description
    for file_name, description in files_basename.items()
}

# Print or use the updated filenames
for file_name, description in files.items():
    print(file_name, ":", description)

dfs = {}
for filename, key in files.items():
    filepath = os.path.join(data_folder, filename)
    df = pd.read_excel(filepath)
    dfs[key] = df


# Filter the assignment_details dataframe to retain only rows where assignment_id == 2078996
# assignment_details = dfs['assignment_details']
# dfs['assignment_details'] = assignment_details[assignment_details['assignment_id'] == 2078996]



# Generation configuration
generation_config = {
    "temperature": 1,
    "top_p": 0.96,
    "top_k": 16,
    "max_output_tokens": 800, #(1 token approx 0.75 words)
    "response_mime_type": "text/plain",
}

# Create the model once before the loop
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash", # "gemini-1.5-flash"
    generation_config=generation_config,
)


# Function to make API calls with retries and delay
def generate_with_retry(model, contents, retries=5):
    attempt = 0
    while attempt < retries:
        try:
            # Correct call: pass contents and NO generation config here
            response = model.generate_content(contents=contents) 
            time.sleep(5)
            return response
        except Exception as e:
            error_message = str(e)
            if "429" in error_message or "Resource has been exhausted" in error_message:
                print("Received 429 error. Waiting for 60 seconds before retrying...")
                time.sleep(60)  # Wait 1 minute
                attempt += 1
            else:
                print(f"An error occurred: {e}")
                time.sleep(60)  # Wait 1 minute
                attempt += 1
    print("Max retries exceeded.")
    return None

# Initialize a list to store the summary text.
detailed_text = []

# Create an empty list to store the results and token usage
results = []
token_usage = []  

# Prepare the system prompt
system_prompt = """
You are a mathematics school teacher looking to understand data from an assignment report to help your students. 
Write concisely and simply without any markup language.
It is IMPORTANT that you provide a concise and abstractive summary of the findings in under 120 words.
Focus on the problems and students that are not doing well, and explain why these specific students or problems might not be doing well if possible.
Positive examples:
(Example 1: 
Students A2a4 and student Ba4e44 are not doing well because they had difficulty with problems 1 and 2, requiring more than 4 attempts and these problems are related to common core 6.RP.A.1 understanding and describing ratios.
Example 2:
Problems 3 and 4 were especially challenging for most students, with more than half the students requiring 2 or more attempts to answer them correctly eventually. They also spent more than 5 minutes on average on this problem.
Example 3:
Problems 1a was difficult for many students, with Student K, Student H, Student M requiring 2 or more hints to answer the question correctly eventually. 
Example 4:
Student a45Fe did not do well on the assignment, scoring less than 40 percent on the non-open response problems attempted. In fact, the time used was especially short, compared to other students, suggesting that the student may not have spent enough time on the assignment.
Example 5:
Many students incorrectly answered "9" for problem 1. You may need to reteach scale drawing and proportional relationships.
Example 6:
Students struggled with problems 3 and 5. Over 40 percent of the class needed hints or multiple tries.
Example 7:
Students ad245, s422g4 and Cad34 didnt do well on the assignment. It seems like they finished it quickly, which might mean they didn't put in their best effort.
)

However, the following examples are NOT allowed, as the use of "some" students or "some" problems are too vague and not helpful.
Also, do NOT provide general advice on what to do, but rather focus on the specific students and problems.
Negative examples:
(Example 1: 
The assignment revealed that some students might be struggling with concepts related to ratios and scale drawings. 
Example 2:
Providing additional support and resources, focusing on areas like 6.RP.A.1, 6.RP.A.3a, and 7.G.A.1, could benefit some of these students. 
)
If there are students doing much better or worse than past performance, mention these specific students.
As much as possible, identify specific students or problems and not use "some" students or "some" problems.
Note that all the problems discussed are non-open response problems, and that the average score is NOT the percentage of problems completed correctly.

Finally, the summary should have short headers (e.g., "Problems to note", "Students to note"), with bullet points for the findings.
MOST Importantly, the concise and abstractive summary should be no more than 120 words.

"""
# Function to convert DataFrame to a text
def df_to_string(df):
    if df.empty:
        return "No data available."
    df_string = df.to_json(orient="records", indent=2)
    return df_string


def gen_assignment_summary(asg_details):
    try:
        median_time = asg_details['median_assignment_completion_minutes'].iloc[0]
        med_time_float = float(median_time)
        rounded_median = round(med_time_float, 2)
        return f"Median time it took to finish the assignment is {rounded_median} minutes"
    except:
        return ""
    
def gen_student_summary(student_details, threshold = 0.8):
    filtered_students = student_details[student_details['student_average_score_out_of_problems_attempted'] <= threshold]
    student_xref_array = ', '.join(filtered_students['student_xref'].astype(str))
    ans = f"""Students {student_xref_array} struggled with the assignment. Their scores were below {threshold * 100}%."""
    return ans



def sort_by_problem_pos(item):
    # Separate numeric and alphabetic parts
    num_part = int(''.join(filter(str.isdigit, item)))  # Extract numeric part
    char_part = ''.join(filter(str.isalpha, item))      # Extract alphabetic part
    
    # Return a tuple to sort by numeric part first, then alphabetic part
    return (num_part, char_part)
    
# a3
def gen_problem_high_lvl_summary(problem_details, threshold = 0.8):
    """
        Students struggled with problems "p1", "p2" and "p3". 
        Over 40% of the class needed hints and over 30% needed multiple tries.
    """
    filtered_problems = problem_details[problem_details['problem_proportion_students_correct'] <= threshold]
    
    upper_bound_correct_eventually = 0
    upper_bound_wrong= 0
    
    for ind in filtered_problems.index:
        curr_correct_eventually_percent = filtered_problems['problem_proportion_students_correct_eventually'][ind]
        curr_wrong_percent = filtered_problems['problem_proportion_students_incorrect'][ind]
        upper_bound_correct_eventually = max(upper_bound_correct_eventually, curr_correct_eventually_percent)
        upper_bound_wrong = max(upper_bound_wrong, curr_wrong_percent)

    
    problem_num = ','.join(map(str, sorted(filtered_problems['problem_position'].to_numpy(), key=sort_by_problem_pos)))
    reply = f"""Students struggled with problems {problem_num}."""
    
    if upper_bound_correct_eventually > 0:
        reply += f""" While up to {round(upper_bound_correct_eventually * 100, 0)}% of the class were correct eventually,"""

    if upper_bound_wrong > 0:
        reply += f""" up to {round(upper_bound_wrong * 100, 0)}% of the class did not manage to get the problem correct at all."""
    return reply

# a3
def gen_problem_low_lvl_summary(problem_details, threshold = 0.8):
    filtered_problems = problem_details[problem_details['problem_proportion_students_correct'] <= threshold]
    llm_understandable = []
    for index, row in filtered_problems.iterrows():
        row_map = {}
        row_map["Problem"] = row['problem_position']
        row_map["Problem text"] = row['problem_text']
        row_map["Problem type"] = row['problem_type']
        
        if not pd.isnull(row["correct_answer"]):
            row_map["Correct answer"] = row["correct_answer"]

        if not pd.isnull(row["common_wrong_answer"]):
            row_map["Common wrong answer among students"] = row['common_wrong_answer']
         
        llm_understandable.append(row_map)

    prompt = f"Given the following problems students struggled with: {llm_understandable}. Identify what concepts students struggled with under 100 words or less."
    
    return prompt

# Loop over each row in assignment_details
for index, assignment_row in dfs['assignment_details'].iterrows():
    assignment_id = assignment_row['assignment_id']

    print(f"Processing assignment {assignment_id} (Index {index + 1}/{len(dfs['assignment_details'])})")

    # Extract corresponding data
    assignment_summary = dfs['assignment_details'][dfs['assignment_details']['assignment_id'] == assignment_id]
    student_summary = dfs['student_details'][dfs['student_details']['assignment_id'] == assignment_id]
    problem_summary = dfs['problem_details'][dfs['problem_details']['assignment_id'] == assignment_id]
    student_problem_details = dfs['student_problem_details'][dfs['student_problem_details']['assignment_id'] == assignment_id]

    

    # Check if the number of students who started the assignment is zero
    if assignment_row['number_students_started_assignment'] == 0:
        summarized_result = "No students started the assignment."
        total_token_count = 0
        prompt_token_count = 0
        candidates_token_count = 0
        # Append the token counts to the token_usage list
        token_usage.append({
            "assignment_id": assignment_id,
            "total_token_count": total_token_count,
            "prompt_token_count": prompt_token_count,
            "candidates_token_count": candidates_token_count,
        })

        # Append the result to the results list
        results.append({
            "assignment_id": assignment_id,
            "summarized_result": summarized_result,
        })
    else:
        summary1 = gen_assignment_summary(assignment_summary) + "\n\n" + gen_student_summary(student_summary) + "\n\n" + gen_problem_high_lvl_summary(problem_summary)
        # Call the Gemini API to summarize
        prompt1 = gen_problem_low_lvl_summary(problem_summary)
        response = generate_with_retry(model, contents=prompt1) # Get the response object

        if response:
            summary2 = response.text
            usage = response.usage_metadata  # Access usage metadata
            total_token_count = usage.total_token_count
            prompt_token_count = usage.prompt_token_count
            candidates_token_count = usage.candidates_token_count
            detailed_text.append({
                "assignment_id": assignment_id,
                "user_prompt": prompt1
            })

            summarized_result = summary1 + "\n\n" + summary2

            # Append the token counts to the token_usage list
            token_usage.append({
                "assignment_id": assignment_id,
                "total_token_count": total_token_count,
                "prompt_token_count": prompt_token_count,
                "candidates_token_count": candidates_token_count,
            })

            # Append the result to the results list
            results.append({
                "assignment_id": assignment_id,
                "summarized_result": summarized_result,
            })
        else:  # Handle the case where generate_with_retry returns None (max retries exceeded)
            summarized_result = "Summary generation failed after multiple retries."
            total_token_count = 0
            prompt_token_count = 0
            candidates_token_count = 0
            token_usage.append({
                "assignment_id": assignment_id,
                "total_token_count": total_token_count,
                "prompt_token_count": prompt_token_count,
                "candidates_token_count": candidates_token_count,
            })
            results.append({
                "assignment_id": assignment_id,
                "summarized_result": summarized_result,
            })
            print(f"Summary generation failed for assignment {assignment_id} after multiple retries.")
# Create a DataFrame from the results
results_df = pd.DataFrame(results)
# Create a DataFrame from the full text.
fulltext_df = pd.DataFrame(detailed_text)
token_usage_df = pd.DataFrame(token_usage)  # DataFrame for token counts


results_df.to_excel(output_file, index=False)
fulltext_df.to_excel(output_text, index=False)
token_usage_df.to_excel(token_file, index=False)  # Save token counts


# Print a completion message
print(f"All summaries have been generated and saved to '{output_file}'.")
