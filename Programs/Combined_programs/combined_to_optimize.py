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
    """Your job is to reason about whether an additional column should be generated or if a question should be directly answered using a SQLite query, follow these heuristics:

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
    This applies even to close matches (amount is present), but the questions is refering to amount_min or amount_last, which are not present in the database.
    """
    question = dspy.InputField()
    available_columns = dspy.InputField(desc="Information about the database and its tables")
    reasoning = dspy.OutputField(desc="Reasoning about which decision to make based on the question and available columns.")


class PM_combined(dspy.Module):
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
        self.pm_sql = PM_SQL_multi_sp(pool=self.pool, rm = self.rm)
        self.pm_sql.load(path=pm_sql_path)
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
        
        
        if check.decision.decision.lower() == "yes":
            print("calling sql module, question: ", question)
            try:
                if columns_to_generate and len(columns_to_generate) > 0:
                    self.col_tacked[question].append("FP")
                    print("Should have said NO, required columns to generate")
            except:
                self.col_tacked[question].append("TP")
                pass

            try:
                if not columns_to_generate or len(columns_to_generate) == 0:
                    self.col_tacked[question].append("TP")

            except:
                self.col_tacked[question].append("TP")
                pass
                    
            result = self.pm_sql(self.question)
            return result
            
        else:
            if columns_to_generate:
                print("there are column to generate")
                self.col_tacked[question].append("TN")
                instructions = self.dp_graph.instructions_c(columns_to_generate)
            #definitions = self.dp_graph.definitions_s(columns_to_generate)

                for instruction in instructions:
                    print("calling python module cols to generate: ", columns_to_generate)
                    
                    descript = self.pm_py(instruction) # if it fails, it should not write into rm that the column exists
                print("finished calling python, now calling sql module")
                result = self.pm_sql(question)
                return result
            else:
                print("it wanted to generate collumns for something that did not require it")
                print("calling sql module instead")
                self.col_tacked[question].append("FN")
                return self.pm_sql(question)
    def get_col_tracked(self):
        return self.col_tacked
        