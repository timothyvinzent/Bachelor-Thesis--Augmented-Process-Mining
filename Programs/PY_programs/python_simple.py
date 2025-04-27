from collections import defaultdict
import copy
import dspy
from pydantic import BaseModel
import sqlite3
import traceback

def check_beginning(generated):
    # generated must beginn with - '
    if not generated.startswith("- '"):
        return False
    else:
        return True
# add a test to check for "-" in the string after the first occurance of "- '"

def check_column_type(col_type):
    if col_type == "INTEGER":
        return True
    elif col_type == "BOOLEAN":
        return True
    elif col_type == "DATETIME":
        return True
    else:
        return False

def check_column_name(col_name, instruction):
    # must be a single word and present within the instruction
    if len(col_name.split()) == 1 and col_name in instruction:
        return True
    else:
        return False
    


# class PythonCode(BaseModel):
#     python : str

# class Generate(dspy.Signature):
#     """Based on an instruction to create a new column, generate Python code to execute instruction"""
#     column_description = dspy.InputField(desc="Information about the database and its tables")
#     instruction = dspy.InputField()
#     generated_code: PythonCode = dspy.OutputField(desc="Python code which will be executed to fulfill instruction, for boolean columns only output boolean values (not integers)")

# class Extract(dspy.Signature):
#     """Extract the name of the column and the SQLITE type of the column based on the instruction"""
#     instruction = dspy.InputField()
#     new_column_name = dspy.OutputField(desc="Only write the name of the new column to be added to the database")
#     column_type_in_sql = dspy.OutputField(desc="[INTEGER, BOOLEAN, DATETIME]")

# class Answer(dspy.Signature):
#     """Given the generated_code, the instruction and column descriptions, provide a short and to the point description of the column which was added to the database in the same format previous columns have been described."""
#     generated_code = dspy.InputField()
#     instruction = dspy.InputField()
#     column_description = dspy.InputField(desc="Information about the database and its tables")
#     description = dspy.OutputField(desc="Short description of the column added to the dataframe using the same format as the previous columns.")


class PM_PY_simple(dspy.Module):
    def __init__(self, rm, conn_path=None):
        super().__init__()
        
        self.conn_path = conn_path
        #self.conn = sqlite3.connect(self.conn_path)
        self.GENERATE = dspy.Predict('column_description, instruction -> generated_code')
        self.EXTRACT = dspy.Predict('instruction -> new_column_name, column_type_in_sql')
        self.ANSWER = dspy.Predict('generated_code, instruction, column_description -> description')
        self.rm = rm
        self.read_write = """The following lines of code are required to read from the database and write the new column to the database:
        import pandas as pd
        query = 'SELECT * FROM event_log'
        dp = pd.read_sql_query(query, conn, parse_dates=['time_timestamp'])
        for cols in dp.columns:
            if dp[cols].isin([0,1]).all() and not cols.endswith("_count"):
                dp[cols] = dp[cols].astype(bool)

        ### Create new column based on the instructions ### Insert pandas code here.## 
        # Unless when creating a new column that is a datetime or boolen, always use .fillna(0).astype(int) to ensure that the column is of integer type and has no NaN values.
        # In case of integer column, use fillna(0).astype(int) in a second line, after the new column has been created. (chained single line operations are not reliable)

        
        ### Closely follow the code below and only change the column name and the column type if needed ### Never use case_concept_name to join the event_log table and the temp_table
        # Update the database table with the new column now refered to as new_column but you should use the actual name of the new column
        cur = conn.cursor()
        cur.execute("ALTER TABLE event_log ADD COLUMN new_column INTEGER")  # Assuming "new_column" is an integer type, change to the actual type of the new column
        dp.to_sql('temp_table', conn, if_exists='replace', index=False)
        conn.commit()
        """
        
        self.counter = 0
        self.code = defaultdict(list)
        self.errors = defaultdict(list)
        self.descriptions = defaultdict(list)
    def get_connection(self):
        return sqlite3.connect(self.conn_path)

    def __deepcopy__(self, memo):
        # Create a new instance of the class
        cls = self.__class__
        result = cls.__new__(cls)
        
        # Copy all attributes except for 'conn'
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            if k == 'conn':
                setattr(result, k, None)  # or reinitialize the connection if needed
            elif k == 'rm':
                setattr(result, k, None)
            else:
                try:
                    setattr(result, k, copy.deepcopy(v, memo))
                except Exception as e:
                    print("k", k)
                    print("type of k", type(k))
                    print("v", v)
                    print("type of v", type(v))
        
        # Optionally, reinitialize the connection if needed
        if self.conn_path:
            result.conn = sqlite3.connect(self.conn_path)
            result.rm = self.rm
        
        return result
    def trace_prettyprint(self, tb, python_code, error_code_fail):
        
    # Format the stack trace to include line number and code context
        formatted_tb = []
        for frame in tb:
            if frame.filename == '<string>':
                line_number = frame.lineno
                code_lines = python_code.split('\n')
                error_line = code_lines[line_number - 1] if line_number <= len(code_lines) else "Line number out of range"
                formatted_tb.append(f"Line {line_number}: {error_line}")
        formatted_tb_str = "\n".join(formatted_tb)
        formatted_error = error_code_fail + "\n" + "Stack trace:" + "\n"+ formatted_tb_str
        
        return formatted_error


    def forward(self, instruction):
        """Generates Python code to generate a new column in the database and returns a description of the column"""
        instruct = self.read_write + "\n" + instruction
        self.column_description = self.rm.retrieve(instruction)
        temp_code_hist = []
        conn = self.get_connection()
        extracted = self.EXTRACT(instruction=instruction)
        pre_float_check = True
        pre_distinc_value_check = True
        distinc_values = [(0,), (1,)]
        

        dspy.Suggest(
            check_column_type(extracted.column_type_in_sql),
            "Column type must be either INTEGER, BOOLEAN or DATETIME",
        )
        dspy.Suggest(
            check_column_name(extracted.new_column_name, instruction),
            "Column name must be a single word and present in the instruction",
        )
        
            
        result = self.GENERATE(instruction=instruct, column_description=self.column_description)
        cur = conn.cursor()
        #cur.execute("DROP TABLE IF EXISTS temp_table;")
        #conn.commit()
        num_gen = 0
        num_errors = 0
        num_gen += 1
        python_code = result.generated_code
        # remove ```python and ``` from the generated code
        python_code = python_code.replace("```python", "")
        python_code = python_code.replace("```", "")
        col_name = extracted.new_column_name
        cur.execute("PRAGMA table_info(event_log);")
        columns_pragma = [info[1] for info in cur.fetchall()]


        if col_name in columns_pragma:
            # Drop the column if it exists
            cur.execute(f"ALTER TABLE event_log DROP COLUMN {col_name};")
            conn.commit()
        # if dp in local scope, deleted it
        if "dp" in locals():
            del dp
            print("deleted dp")
        
        col_type = extracted.column_type_in_sql
        self.code[instruction].append(python_code)
        temp_code_hist.append(python_code)
        commit_to_db = f"""cur.execute('CREATE INDEX idx_case_concept_name_temp_table ON temp_table(case_concept_name);')\nconn.commit()\ncur.execute('ALTER TABLE temp_table ADD COLUMN idt INTEGER;')\nconn.commit()\ncur.execute('''UPDATE temp_table SET idt = (SELECT rowid FROM (SELECT ROW_NUMBER() OVER (ORDER BY case_concept_name, time_timestamp) as seq_num, rowid FROM temp_table) temp WHERE temp.rowid = temp_table.rowid);''')\nconn.commit()\ncur.execute('CREATE INDEX idx_temp_table_idx ON temp_table(idt);')\nconn.commit()\ncur.execute('VACUUM;')\ncur.execute('ANALYZE;')\nconn.commit()\nquery = '''UPDATE event_log SET {col_name} = (SELECT {col_name} FROM temp_table WHERE event_log.idx = temp_table.idt) WHERE EXISTS (SELECT 1 FROM temp_table WHERE event_log.idx = temp_table.idt);'''\ncur.execute(query)\nconn.commit()\ncur.close()"""
        self.commit_to_db = commit_to_db
        #\ncur.execute('DROP TABLE temp_table')
        local_scope = {"conn": conn, "cur": cur}
        cause_error = True
        error_code_fail = ""
        error_col_fail = ""
        formatted_error = ""
        try:
            exec(python_code, globals(), local_scope)
        except Exception as e:
            tb = traceback.extract_tb(e.__traceback__)
            error_code_fail = str(e)
            formatted_error = self.trace_prettyprint(tb, python_code, error_code_fail)
            cause_error = False
            self.errors[instruction].append(formatted_error) # str(e)
            #cur.execute("DROP TABLE IF EXISTS temp_table;")
            #conn.commit()

        dspy.Suggest(
            cause_error,
            "Error executing code" + formatted_error,
            
        )
        cause_error = True


        try:
            dp = local_scope["dp"]
            dp.to_sql("temp_table", conn, if_exists="replace", index=False)
            print("length of dp", len(dp))
        except:
            pass

        dspy.Suggest(
                len(dp) == 561470,
                "Your generated Dataframe has the wrong length, make sure not to shorten dp, expected 561470, received " + str(len(dp)),
            )
        
        
        try:
            print("column type of new column", dp[col_name].dtype)
        except Exception as e:
            
            error_col_fail = str(e)
            cause_error = False
            self.errors[instruction].append(str(e))
            #cur.execute("DROP TABLE IF EXISTS temp_table;")
            conn.commit()
        dspy.Suggest(
            cause_error,
            "New Column was not successfully generated, " + error_col_fail,
        )
        cause_error = True

        
        try:
            pre_float_check = dp[col_name].dtype == "float64" or dp[col_name].dtype == "object"
            pre_float_check = not pre_float_check
            #pre_object_check = not dp[col_name].dtype == "object"
            #together_check= not pre_float_check == False or not pre_object_check == False
        except:
            pass
        print("pre_float_check", pre_float_check)
        dspy.Suggest(
            pre_float_check,
            "Do not use .apply and lambda functions to create the new column, as those will result in nan values when grouping by case (subsequent column dtype will be float64 or object). Instead use boolean operators first and subsequently group by case, then counring using for example value_counts() or methods that are more robust in avoiding nan values. (fillna(0).astype(int) will most likely also be incorrect.)",
            
        )
        cur = conn.cursor()
        try:
            cur.execute(f"SELECT DISTINCT {col_name} FROM temp_table;")
            distinc_values = cur.fetchall()
            pre_distinc_value_check = not any(isinstance(i[0], type(None)) for i in distinc_values)
        except Exception as e:
            self.errors[instruction].append(str(e))

            pass
        print("pre_distinc_value_check", pre_distinc_value_check)
        dspy.Suggest(
            pre_distinc_value_check, # sends back to EXTRACT
            "There are nan values present in the new column, this is forbidden, use different transformation in the python code that will avoid resulting in nan values. For example try an alternative to using 'apply' method and lambda functions. Simply using 'fillna(0).astype(int)' will most likely also be wrong (fix the logical error in your approach instead) (i.e using value_counts() or something like that).",
        )

        try:
            exec(commit_to_db) # requires a temp table to be present, we overwrite the temp table anyhow whenever python exec is called
        except Exception as e:
            self.errors[instruction].append(str(e))
            pass
        if len(temp_code_hist) > 3:
            python_code = "Error: " + "function failed to execute"
        pred = self.ANSWER(generated_code=python_code, instruction=instruction, column_description=self.column_description)
        test = len(pred.description) <= 350
        dspy.Suggest(
            test,
            "Column description must be short and less than 350 characters",
        )
        dspy.Suggest(
            check_beginning(pred.description),
            "Column description must start with - '",
        )
        try:
            self.descriptions[instruction].append(pred)
        except Exception as e:
            self.errors[instruction].append(str(e))
            return "Error generating the column description"
        self.rm.add_new(pred.description) #turn off during training
        return pred

    def get_history(self):
        return self.code, self.errors, self.descriptions

    def get_column_description(self):
        return self.column_description
