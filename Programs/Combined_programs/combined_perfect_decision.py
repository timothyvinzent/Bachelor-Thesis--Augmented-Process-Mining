# adjust the json files to the correct path

from collections import defaultdict
from pydantic import BaseModel
import dspy
from enum import Enum
from PY_programs.python_tables import PM_PY_no_deep
from SQL_programs.sql_reasoning import PM_SQL_multi_sp

class Decision(str, Enum):
    YES = "yes"
    NO = "no"

class binary_decision(BaseModel):
    decision: Decision

class Check(dspy.Signature):
    """Your job is to determine whether an additional column should be generated or if a question should be directly answered using a SQLite query, follow these heuristics:

    1. Repeated Complex Calculations: If a potential query involves repeated complex calculations or aggregations, we generate additional columns to store these pre-computed values. 
    This reduces the need for complex logic in the query itself.

    2. Data Completeness: Potential queries must account for all relevant cases, including those where certain events do not occur. 
    If a potential query might miss cases due to filtering, we pre-compute and store the necessary information in a new column.

    3. Simplify Aggregations: If a potential query requires multiple levels of aggregation (multiple boolean or other conditions), we generate columns that store intermediate results (boolean columns, or event counts) to simplify the final query.

    4. Minimize Logical Steps: We reduce the number of logical steps in potential queries by pre-computing values that require complex logic, 
    making the queries simpler and less error-prone.

    5. Readability and Maintainability: If a query becomes difficult to read and maintain due to its complexity, we generate additional columns. 
    Simpler queries are easier to debug and less likely to contain logical errors.

    By following these guidelines, we can ensure that our queries remain simple, maintainable, and accurate, reducing the likelihood of logical mistakes.
    If it appears that a question is referring to columns that are not present in the database, additional columns should allways be generated to provide the necessary information.
    This applies even to close matches (amount is present), but the questions is refering to amount_min or amount_last, which are not present in the database."""

    question = dspy.InputField()
    available_columns = dspy.InputField(desc="Information about the database and its tables")
    provided_reasoning = dspy.InputField(desc="Thinking that your colleague has done to arrive at the decision. You may use this to help you make your decision.")
    decision: binary_decision = dspy.OutputField(desc="Indicate whether the question can be answered directly using a SQLite query 'yes' or if additional columns should be generated 'no'.")

class Think(dspy.Signature):
    """Determine whether an additional column should be generated or if a question should be directly answered using a SQLite query, with a cautious approach as per the following heuristics:

    - **Repeated Complex Calculations**: Generate additional columns if potential queries involve repeated calculations or aggregations to store pre-computed values. This reduces complex logic in the query.

    - **Data Completeness**: Ensure queries account for all relevant cases, including where certain events do not occur. Pre-compute and store necessary information in a new column if a query might miss cases or events due to filtering.

    - **Simplify Aggregations**: Generate columns to store intermediate results (like boolean columns or event counts) if a query requires aggregation, simplifying the final query.

    - **Minimize Logical Steps**: Pre-compute values requiring logic to reduce logical steps in queries, making them simpler and less error-prone.

    - **Readability and Maintainability**: Generate additional columns if a query becomes difficult to read and maintain due to their length. Simpler queries are easier to debug and less likely to contain logical errors.

    - **Risk of Direct Queries**: Only opt for a SQL query directly if it is safe and extremely unlikely to cause an error or logical mistake. Generating additional columns is always a safe bet with no negative consequences. We want to avoid failure as much as possible. Even if we have all the columns required to write a SQLite query, it could be safer to outsource any additional operations to an expert column generator.

    - **Missing Columns**: Generate additional columns if questions refer to columns not present in the database, even with close matches (e.g., "amount_min" or "amount_last" if only "amount" is present).

    # Steps

    1. Analyze the complexity of the potential query and identify any repeated calculations or intricate logic.
    2. Check if the potential query covers all relevant data cases, including unoccurring events.
    3. Consider the aggregation levels involved and simplify by pre-computing when necessary.
    4. Evaluate the logical steps required in the query and minimize them by generating additional columns.
    5. Assess the query for readability and maintenance concerns, opting for column generation if it enhances clarity.
    6. Verify the presence of necessary columns in the database; generate columns for missing ones referenced in the question.
    7. Critically evaluate the risk of directly answering with a SQL query and ensure it is only chosen when truly safe.

    # Output Format

    Provide a detailed explanation of your assessment followed by your decision: "Generate Additional Columns" or "Answer with SQLite Query".

    # Notes

    - If the required column is not present in the database, always opt for generating additional columns.
    - Consider the maintainability and readability of queries as a factor for decision-making.
    - Always provide a clear reasoning process before concluding to justify the decision effectively.
    - Be particularly cautious when deciding to opt for a direct SQL query and ensure all safety measures are thoroughly considered.
    - As a rule of thumb, anything related to money, balances and amounts should be handled by generating additional columns to avoid any potential errors and discrepancies (really important not to take any risk).
    """
    question = dspy.InputField()
    available_columns = dspy.InputField(desc="Information about the database and its tables")
    reasoning = dspy.OutputField(desc="Reasoning about which decision to make based on the question and available columns.")


class PM_combined_perfect_d(dspy.Module):
    def __init__(self, dp_graph, rm, pool, conn_path, pm_py_path, pm_sql_path): # requires all the create column instructions to retrieve the correct instructions for missing cols
        super().__init__()
        self.dp_graph = dp_graph
        self.think = dspy.Predict(Think)

        self.check = dspy.Predict(Check)
        self.rm = rm
        self.pool = pool
        self.conn_path = conn_path
        self.pm_py = PM_PY_no_deep(rm = self.rm, conn_path= self.conn_path )
        self.pm_py.load(path=pm_py_path)
        #pm_py._compiled = True
        
        #pm_sql = assert_transform_module(PM_SQL_multi_sp(pool=self.pool, rm = self.rm), functools.partial(backtrack_handler, max_backtracks=3))
        self.pm_sql = PM_SQL_multi_sp(pool=self.pool, rm = self.rm)
        self.pm_sql.load(path=pm_sql_path)
        #pm_sql._compiled = True 
        self.col_tacked = defaultdict(list)

    def forward(self, question, req_cols):

        self.question = question
        available_cols = self.rm.cols
        columns_to_generate = None
        if type(req_cols) == str:
            columns_to_generate = self.dp_graph.cols(req_cols[2:-2].split("', '"), available_cols)

        

        col_descriptions = self.rm.retrieve(question)

        thoughts = self.think(question = question, available_columns = col_descriptions)
        check = self.check(question = question, available_columns = col_descriptions, provided_reasoning = thoughts.reasoning)
        print("check", check.decision.decision)
        dspy.Suggest(
            check.decision.decision.lower() == "yes" or check.decision.decision.lower() == "no",
            "The response can only be 'yes' or 'no'.",
        )
        
        if columns_to_generate and len(columns_to_generate) > 0:
            if check.decision.decision.lower() == "yes":
                self.col_tacked[question].append("FP")
            else:
                self.col_tacked[question].append("TN")
            
            instructions = self.dp_graph.instructions_c(columns_to_generate)
        #definitions = self.dp_graph.definitions_s(columns_to_generate)
            for instruction in instructions:
                print("calling python module cols to generate: ", columns_to_generate)
                descript = self.pm_py(instruction)
            print("finished calling python, now calling sql module")
            result = self.pm_sql(question)
            return result
        else:
            if check.decision.decision.lower() == "yes":
                self.col_tacked[question].append("TP")
                result = self.pm_sql(self.question)
                return result
            else:
                self.col_tacked[question].append("FN")
                result = self.pm_sql(self.question)
                return result

    def get_col_tracked(self):
        return self.col_tacked
        