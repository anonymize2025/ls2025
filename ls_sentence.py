import os
import pandas as pd
import google.generativeai as genai
import warnings
import time

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
output_file = './data/output/sentence/assignment_summaries.xlsx'
output_text = './data/output/sentence/assignment_detailed_text.xlsx'
token_file = './data/output/sentence/token_count.xlsx'

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



# Define the function to generate a summary text for each row with NaN handling
def generate_summary_assignment(row):
    summary = ""
    summary += f"The assignment name is {row['assignment_name']}.\n"

    # Check if number of students given the assignment is NaN
    if pd.notna(row.get('number_students_given_assignment')):
        summary += f"With {row['number_students_given_assignment']} students given the assignment, "
    else:
        summary += "The total number of students given the assignment is not available, "

    # Check if number of students not started is NaN
    if pd.notna(row.get('number_students_not_started_assignment')):
        summary += f"we note that {row['number_students_not_started_assignment']} have not started the assignment.\n"
    else:
        summary += "the number of students who have not started the assignment is not available.\n"

    # Check if number of students started is NaN
    if pd.notna(row.get('number_students_started_assignment')):
        summary += f"Nonetheless, {row['number_students_started_assignment']} students started the assignment, "
    else:
        summary += "The number of students who started the assignment is not available, "

    # Check if number of students completed is NaN
    if pd.notna(row.get('number_students_completed_assignment')):
        summary += f"of which {row['number_students_completed_assignment']} completed it.\n"
    else:
        summary += "and the number of students who completed the assignment is not available.\n"

    # Check if percentages are NaN
    if pd.notna(row.get('percent_students_started')) and pd.notna(row.get('percent_students_completed')):
        summary += (
            f"This meant that {round(row['percent_students_started'] * 100, 2)} % of the students started the assignment, "
            f"and {round(row['percent_students_completed'] * 100, 2)} % completed it.\n"
        )
    else:
        summary += "The percentage of students who started and completed the assignment is not available.\n"

    # Check if median completion time and time per problem are NaN
    if pd.notna(row.get('median_assignment_completion_minutes')) and pd.notna(row.get('time_minutes_per_problem')):
        summary += (
            f"Of those students who completed the assignment, the median time taken was approximately "
            f"{round(row['median_assignment_completion_minutes'])} minutes, "
            f"i.e., approximately {round(row['time_minutes_per_problem'], 1)} minutes per problem/problem part.\n"
        )
    else:
        summary += "The median time taken and time per problem for those who completed the assignment are not available.\n"

    return summary



def generate_summary_problem(problem_df):
    """Generates a summary for problem_summary_nonopen DataFrame."""
    summaries = []
    for _, row in problem_df.iterrows():
        # Concatenate problem ID for consistent use
        problem_id = f"{row['problem_position']} ({row['problem_xref']})"
        
        # Check if 'problem_average_score' is NaN
        if pd.isna(row['problem_average_score']):
            # Append statements for problems with NaN average score
            summaries.append(
                f"Problem {problem_id} did not have an average score recorded, which means no students completed this problem.\n"
            )
        elif row['problem_average_score'] < 0.3:
            # Append statements for problems with average score below 0.3
            summaries.append(
                f"Problem {problem_id} was especially challenging for the {row['problem_n_student_count']} student(s) who attempted this problem, suggesting common core {row['problem_common_core_plus_code']} {row['problem_common_core_plus_skill_name']} may need to be reviewed. It had an average score of {round(row['problem_average_score'] * 100, 2)}%.\n"
                f"For problem {problem_id}, tt had {row['problem_total_students_correct']} students who answered correctly on the first attempt, "
                f"{row['problem_total_students_correct_eventually']} students who answered correctly eventually, and "
                f"{row['problem_total_students_incorrect']} students who answered incorrectly with the answer shown.\n"
                f"For the students who completed this problem {problem_id}, the median completion time was {row['median_problem_completion_minutes']} minutes.\n"
                f"For problem {problem_id}, the total number of attempts and hints were {row['problem_total_attempt_count']} and  {row['problem_total_hint_count']}, which meant an average of {row['problem_average_attempt_count']} attempts and  {row['problem_average_hint_count']} hints.\n"
            )
            if pd.notna(row['common_wrong_answer']):
                summaries.append(
                    f"For problem {problem_id}, the most common wrong answer was {row['common_wrong_answer']}."
                    f"For problem {problem_id}, which asked the question {row['problem_text']} (where the correct answer is {row['correct_answer']}), the most common wrong answer {row['common_wrong_answer']} may suggest a weakness in understanding of some concepts related to common core {row['problem_common_core_plus_code']} {row['problem_common_core_plus_skill_name']}."                    
                )
        elif row['problem_average_score'] < 0.5:
            # Append statements for problems with average score below 0.3
            summaries.append(
                f"Problem {problem_id} was difficult for the {row['problem_n_student_count']} student(s) who attempted this problem, suggesting common core {row['problem_common_core_plus_code']} {row['problem_common_core_plus_skill_name']} may need to be reviewed. It had an average score of {round(row['problem_average_score'] * 100, 2)}%.\n"
                f"For problem {problem_id}, it had {row['problem_total_students_correct']} students who answered correctly on the first attempt, "
                f"{row['problem_total_students_correct_eventually']} students who answered correctly eventually, and "
                f"{row['problem_total_students_incorrect']} students who answered incorrectly with the answer shown.\n"
                f"For the students who completed this problem {problem_id}, the median completion time was {row['median_problem_completion_minutes']} minutes..\n"
                f"For problem {problem_id}, the total number of attempts and hints were {row['problem_total_attempt_count']} and  {row['problem_total_hint_count']}, which meant an average of {row['problem_average_attempt_count']} attempts and  {row['problem_average_hint_count']} hints.\n"
            )
            if pd.notna(row['common_wrong_answer']):
                summaries.append(
                    f"For problem {problem_id}, the most common wrong answer was {row['common_wrong_answer']}."
                    f"For problem {problem_id}, which asked the question {row['problem_text']} (where the correct answer is {row['correct_answer']}), the most common wrong answer {row['common_wrong_answer']} may suggest a weakness in understanding of some concepts related to common core {row['problem_common_core_plus_code']} {row['problem_common_core_plus_skill_name']}."                    
                )
        elif row['problem_average_score'] > 0.85:
            # Append statements for problems with average score below 0.3
            summaries.append(
                f"Problem {problem_id} was generally well done by the {row['problem_n_student_count']} student(s) who attempted this problem. It had an average score of {round(row['problem_average_score'] * 100, 2)}%.\n"
                f"For problem {problem_id}, tt had {row['problem_total_students_correct']} students who answered correctly on the first attempt, "
                f"{row['problem_total_students_correct_eventually']} students who answered correctly eventually, and "
                f"{row['problem_total_students_incorrect']} students who answered incorrectly with the answer shown.\n"
                f"For the students who completed this problem {problem_id}, the median completion time was {row['median_problem_completion_minutes']} minutes.\n"
                f"For problem {problem_id}, the total number of attempts and hints were {row['problem_total_attempt_count']} and  {row['problem_total_hint_count']}, which meant an average of {row['problem_average_attempt_count']} attempts and {row['problem_average_hint_count']} hints.\n"
            )
            if pd.notna(row['common_wrong_answer']):
                summaries.append(
                    f"While problem {problem_id} was generally well done, the most common wrong answer was {row['common_wrong_answer']}."
                    f"For problem {problem_id}, which asked the question {row['problem_text']} (where the correct answer is {row['correct_answer']}), the most common wrong answer {row['common_wrong_answer']} may suggest a weakness in understanding of some concepts related to common core {row['problem_common_core_plus_code']} {row['problem_common_core_plus_skill_name']}."                    
                )
        else:
            # Proceed with the regular summary for problems with a valid average score
            summaries.append(
                f"Problem {problem_id} had an average score of {round(row['problem_average_score'] * 100, 2)}%.\n"
                f"It had {row['problem_total_students_correct']} students who answered correctly on the first attempt, "
                f"{row['problem_total_students_correct_eventually']} students who answered correctly eventually, and "
                f"{row['problem_total_students_incorrect']} students who answered incorrectly with the answer shown.\n"
                f"For the students who completed this problem, the median completion time was {row['median_problem_completion_minutes']} minutes.\n"
            )
            if pd.notna(row['common_wrong_answer']):
                summaries.append(
                    f"For problem {problem_id}, the most common wrong answer was {row['common_wrong_answer']}."
                    f"For problem {problem_id}, which asked the question {row['problem_text']} (where the correct answer is {row['correct_answer']}), the most common wrong answer {row['common_wrong_answer']} may suggest a weakness in understanding of some concepts related to common core {row['problem_common_core_plus_code']} {row['problem_common_core_plus_skill_name']}."                    
                )
    return ''.join(summaries)  # Combine all rows' summaries into a single string



def generate_summary_student(student_df):
    """Generates a summary for student_summary DataFrame."""
    summaries = []
    for _, row in student_df.iterrows():
        student_id = row['student_xref'][:8]

        # Check if 'student_average_score_out_of_problems_attempted' is NaN
        if pd.isna(row['student_average_score_out_of_problems_attempted']):
            # Append a different set of statements for students with NaN scores
            summaries.append(
                f"Student {student_id} did not manage to complete any problems in the assignment.\n"
            )
        elif row['student_completed_assignment'] == 0 and row['student_average_score_out_of_problems_attempted'] < 0.4:
            summaries.append(
                f"Student {student_id} has NOT completed the assignment and did NOT do well on the non-open response problems attempted.\n"
                f"Of the {row['student_number_of_problems_attempted']} non-open response problems attempted, the student {student_id} scored {round(row['student_average_score_out_of_problems_attempted'] * 100, 2)}% on the problems attempted in the assignment, spending {round(row['student_time_spent_on_assignment_minutes'], 1)} minutes working on it.\n"
                f"Student {student_id} used a total of {row['student_total_attempt_count_out_of_problems_attempted']} attempts for the {row['student_number_of_problems_attempted']} problems they worked on, and used a total of {row['student_total_hint_count_out_of_problems_attempted']} hints.\n"
                f"For student {student_id}, that worked out to be an average of {row['student_average_attempt_count_out_of_problems_attempted']} attempts and {row['student_average_hint_count_out_of_problems_attempted']} hints per problem attempted.\n"
                f"In all, student {student_id} had {row['student_total_problem_correct']} problems correct on the first attempt, {row['student_total_problem_correct_eventually']} problems correct eventually, and {row['student_total_problem_incorrect']} problems incorrect where the answer was shown.\n"
            )
        elif row['student_completed_assignment'] == 0:
            summaries.append(
                f"Student {student_id} has NOT completed the assignment.\n"
                f"Nonetheless, of the {row['student_number_of_problems_attempted']} non-open response problems attempted, the student {student_id} scored {round(row['student_average_score_out_of_problems_attempted'] * 100, 2)}% on the problems attempted in the assignment, spending {round(row['student_time_spent_on_assignment_minutes'], 1)} minutes working on it.\n"
                f"Student {student_id} used a total of {row['student_total_attempt_count_out_of_problems_attempted']} attempts for the {row['student_number_of_problems_attempted']} problems they worked on, and used a total of {row['student_total_hint_count_out_of_problems_attempted']} hints.\n"
                f"For student {student_id}, that worked out to be an average of {row['student_average_attempt_count_out_of_problems_attempted']} attempts and {row['student_average_hint_count_out_of_problems_attempted']} hints per problem attempted.\n"
                f"In all, student {student_id} had {row['student_total_problem_correct']} problems correct on the first attempt, {row['student_total_problem_correct_eventually']} problems correct eventually, and {row['student_total_problem_incorrect']} problems incorrect where the answer was shown.\n"
            )
        elif row['student_completed_assignment'] == 1 and row['student_average_score_out_of_problems_attempted'] < 0.4:
            summaries.append(
                f"Student {student_id} has completed the assignment but did NOT do well on the non-open response problems attempted.\n"
                f"Student {student_id} scored {round(row['student_average_score_out_of_problems_attempted'] * 100, 2)}% on the non-open response problems attempted in the assignment, spending {round(row['student_time_spent_on_assignment_minutes'], 1)} minutes working on it.\n"
                #f"Compared to past mean problem performance, student {student_id} scored approximately {round((row['student_average_score_out_of_problems_attempted'] * 100 - row['student_past_average_score'] * 100), 2)}% higher (negative means lower).\n"
                f"Student {student_id} used a total of {row['student_total_attempt_count_out_of_problems_attempted']} attempts for the {row['student_number_of_problems_attempted']} problems they worked on, and used a total of {row['student_total_hint_count_out_of_problems_attempted']} hints.\n"
                f"For student {student_id}, that worked out to be an average of {row['student_average_attempt_count_out_of_problems_attempted']} attempts and {row['student_average_hint_count_out_of_problems_attempted']} hints per problem attempted.\n"
                f"In all, student {student_id} had {row['student_total_problem_correct']} problems correct on the first attempt, {row['student_total_problem_correct_eventually']} problems correct eventually, and {row['student_total_problem_incorrect']} problems incorrect where the answer was shown.\n"
            )
            if row['improvement_compared_to_past_score'] == 1:
                summaries.append(
                    f"Nonetheless, student {student_id} did much better when compared to their past mean problem performance since the start of the academic year.\n"
                )
            elif row['worse_compared_to_past_score'] == 1:
                summaries.append(
                    f"In addition, student {student_id}'s performance in this assignment has dipped, when compared to their past mean problem performance since the start of the academic year.\n"
                )
        elif row['student_completed_assignment'] == 1 and row['student_average_score_out_of_problems_attempted'] > 0.8:
            summaries.append(
                f"Student {student_id} has completed the assignmen and generally did well on the non-open response problems attempted.\n"
                f"Student {student_id} scored {round(row['student_average_score_out_of_problems_attempted'] * 100, 2)}% on the non-open response problems attempted in the assignment, spending {round(row['student_time_spent_on_assignment_minutes'], 1)} minutes working on it.\n"
                #f"Compared to past mean problem performance, student {student_id} scored approximately {round((row['student_average_score_out_of_problems_attempted'] * 100 - row['student_past_average_score'] * 100), 2)}% higher (negative means lower).\n"
                f"Student {student_id} used a total of {row['student_total_attempt_count_out_of_problems_attempted']} attempts for the {row['student_number_of_problems_attempted']} problems they worked on, and used a total of {row['student_total_hint_count_out_of_problems_attempted']} hints.\n"
                f"For student {student_id}, that worked out to be an average of {row['student_average_attempt_count_out_of_problems_attempted']} attempts and {row['student_average_hint_count_out_of_problems_attempted']} hints per problem attempted.\n"
                f"In all, student {student_id} had {row['student_total_problem_correct']} problems correct on the first attempt, {row['student_total_problem_correct_eventually']} problems correct eventually, and {row['student_total_problem_incorrect']} problems incorrect where the answer was shown.\n"
            )
            if row['improvement_compared_to_past_score'] == 1:
                summaries.append(
                    f"In fact, student {student_id} did much better in this assignment when compared to their past mean problem performance since the start of the academic year.\n"
                )
            elif row['worse_compared_to_past_score'] == 1:
                summaries.append(
                    f"Nonetheless, student {student_id}'s performance in this assignment has dipped, when compared to their past mean problem performance since the start of the academic year.\n"
                )
        else:
            # Proceed with the regular summary for students who have attempted problems
            summaries.append(
                f"Student {student_id} completed the assignment.\n"
                f"Student {student_id} scored {round(row['student_average_score_out_of_problems_attempted'] * 100, 2)}% on the non-open response problems attempted in the assignment, spending {round(row['student_time_spent_on_assignment_minutes'], 1)} minutes working on it.\n"
                #f"Compared to past mean problem performance, student {student_id} scored approximately {round((row['student_average_score_out_of_problems_attempted'] * 100 - row['student_past_average_score'] * 100), 2)}% higher (negative means lower).\n"
                f"Student {student_id} used a total of {row['student_total_attempt_count_out_of_problems_attempted']} attempts for the {row['student_number_of_problems_attempted']} problems they worked on, and used a total of {row['student_total_hint_count_out_of_problems_attempted']} hints.\n"
                f"For student {student_id}, that worked out to be an average of {row['student_average_attempt_count_out_of_problems_attempted']} attempts and {row['student_average_hint_count_out_of_problems_attempted']} hints per problem attempted.\n"
                f"In all, student {student_id} had {row['student_total_problem_correct']} problems correct on the first attempt, {row['student_total_problem_correct_eventually']} problems correct eventually, and {row['student_total_problem_incorrect']} problems incorrect where the answer was shown.\n"
            )
            if row['improvement_compared_to_past_score'] == 1:
                summaries.append(
                    f"Student {student_id} did well in this assignment, performing much better in this assignment when compared to their past mean problem performance since the start of the academic year.\n"
                )
            elif row['worse_compared_to_past_score'] == 1:
                summaries.append(
                    f"Student {student_id}'s performance in this assignment has dipped, when compared to their past mean problem performance since the start of the academic year.\n"
                )
    return ''.join(summaries)  # Combine all rows' summaries into a single string   


def generate_summary_student_problem(student_problem_df):
    """Generates a summary for student_problem_details_nonopen DataFrame."""
    summaries = []
    for _, row in student_problem_df.iterrows():
        # Concatenate problem ID for consistent use
        problem_id = f"{row['problem_position']} ({row['problem_xref']})"
        student_id = row['student_xref'][:8]
        # Check if 'problem_average_score' is NaN
        if pd.isna(row['first_action']):
            # Append statements for problems with NaN average score
            summaries.append(
                f"Student {student_id} did not work on problem {problem_id}.\n"
            )
        elif row['saw_answer'] == 1:
            # Append statements for students who saw the answer
            summaries.append(
                f"Student {student_id} was not able to answer problem {problem_id} correctly, and needed the answer to be shown.\n"
            )
        elif row['discrete_score'] == 1:
            # Append statements for students who saw the answer
            summaries.append(
                f"Student {student_id} answered problem {problem_id} correctly on the first attempt without any hints, scoring 100% for the problem, using {round(row['problem_time_in_minutes'],1)} minute(s) approximately.\n"
            )
        elif row['hint_count'] > 0:
            # Append statements for students who saw the answer
            summaries.append(
                f"Student {student_id} scored {round(row['continuous_score'], 2)*100}% for problem {problem_id}, requiring {row['hint_count']} hint(s) and {row['attempt_count']} attempt(s) to answer {problem_id} correctly, using {round(row['problem_time_in_minutes'],1)} minute(s) approximately.\n"
            )
        elif row['attempt_count'] > 0:
            # Append statements for students who saw the answer
            summaries.append(
                f"Student {student_id} scored {round(row['continuous_score'], 2)*100}% for problem {problem_id}, requiring {row['attempt_count']} attempt(s) to answer {problem_id} correctly, though without using any hints, using {round(row['problem_time_in_minutes'],1)} minute(s) approximately. \n"
            )
    return ''.join(summaries)



# Loop over each row in assignment_details
for index, assignment_row in dfs['assignment_details'].iterrows():
    assignment_id = assignment_row['assignment_id']

    print(f"Processing assignment {assignment_id} (Index {index + 1}/{len(dfs['assignment_details'])})")

    # Extract corresponding data
    student_summary = dfs['student_details'][dfs['student_details']['assignment_id'] == assignment_id]
    problem_summary = dfs['problem_details'][dfs['problem_details']['assignment_id'] == assignment_id]
    student_problem_details = dfs['student_problem_details'][dfs['student_problem_details']['assignment_id'] == assignment_id]

    # Generate summaries for each section
    assignment_summary = generate_summary_assignment(assignment_row)
    student_summary_text = generate_summary_student(student_summary)
    problem_summary_text = generate_summary_problem(problem_summary)
    student_problem_summary_text = generate_summary_student_problem(student_problem_details)

    # Add the summary results to the list as a dictionary
    detailed_text.append({
        "assignment_id": assignment_id,
        "assignment_summary": assignment_summary,
        "student_summary_text": student_summary_text,
        "problem_summary_text": problem_summary_text,
        "student_problem_summary_text": student_problem_summary_text
    })


    # Combine all summaries for the assignment
    full_summary = (
        system_prompt +
        "\nAssignment Summary:\n" + assignment_summary +
        "\nProblem Summary:\n" + problem_summary_text +
        "\nStudent Summary:\n" + student_summary_text +
        "\nStudent Problem Details:\n" + student_problem_summary_text
    )


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
        # Call the Gemini API to summarize
        response = generate_with_retry(model, contents=full_summary) # Get the response object

        if response:
            summarized_result = response.text
            usage = response.usage_metadata  # Access usage metadata
            total_token_count = usage.total_token_count
            prompt_token_count = usage.prompt_token_count
            candidates_token_count = usage.candidates_token_count

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
