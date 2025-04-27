from pydantic import BaseModel
import dspy
from collections import defaultdict
from queue import Queue
import threading
import copy


class CodeOutput(BaseModel):
    sql : str

class ReasoningOutput(BaseModel):
    approach : str

class SQL_format(dspy.Signature):
    """Generate a single SQLite query that returns the specific information requested in the question 
    and include relevant details such as duration or amount. When asked about information pertaining 
    to cases (not events), group by case to avoid counting the same case multiple times. Aggregate when necessary,
    using subqueries and outer queries to limit the output size and results in a table that answers the question directly.
    Be aware to make a distinction between questions that ask about cases and question that ask about events, since some of the available columns are aggregated over cases and might lead to wrong results when used in the wrong context."""

    question = dspy.InputField()
    definitions = dspy.InputField(desc="How certain variables are defined, that are not directly present in the database")
    column_description = dspy.InputField(desc="Information about the database and its tables")
    approach = dspy.InputField(desc= "Suggested approach to generate the query")
    sqlite_query: CodeOutput = dspy.OutputField()


class Reasoning(dspy.Signature):
    """Objective: Develop a strategy and logic to create a single SQLite query that will answer a given question.
    Database Information: Use the details about the database and its columns to guide your approach. 
    Be specific about whether the question pertains to "cases" or "events," since every row is an event, and multiple events can be part of a single case.
    Column Details: Some columns contain the same information for each event (row) per case (referred to as "case predicate"). Other columns are independent of cases and refer to events directly.
    You can determine this, based on whether the column description mentions that all values are the same for a case or if the column is aggregated over a case.
    Grouping: When asked about questions independent of cases and you are using a column that is a case predicate, group by case to avoid counting an aggregated value multiple times.
    Do not forget about this for percentage calculations as well (using something like (DISTINCT case_concept_name) FILTER (WHERE col = 1) instead of not grouping by case first for case predicates).
    Query Construction: Do not write the actual query. Instead, provide a detailed explanation of how to construct the query.
    Aggregation: Aggregate data when necessary. Use subqueries and outer queries to limit the output size. Ensure the final result is a table that directly answers the question.
    Some questions might have multiple valid anwers(i.e finding case with highest value x, might have mutliple cases with the same highest value), be aware of this and consider LIMIT 10 instead of LIMIT 1 in such cases.
    """

    # some questions might have multiple valid anwers(i.e finding case with highest value x, might have mutliple cases with the same highest value)
    question = dspy.InputField()
    definitions = dspy.InputField(desc="How certain variables are defined, that are not directly present in the database")
    column_description = dspy.InputField(desc="Information about the database and its tables")
    reasoning: ReasoningOutput = dspy.OutputField()



class Answering(dspy.Signature):
    """Carefully analyze the question and information in the table to form a helpful response. Use all the columns from the table (information) when writing your answer (don't leave away any additional information)."""
    question = dspy.InputField()
    table = dspy.InputField(desc="Pipe deliniated string representing a table.")
    sql = dspy.InputField(desc="SQL query that was executed to generate the table.")
    answer = dspy.OutputField(desc="Only write the answer, not question or table)")  

class PM_isolated(dspy.Module):

    def __init__(self, pool, rm, dp_graph, max_length = 1500):
        super().__init__()

        self.pool = pool
        self.dp_graph = dp_graph
        self.max_length = max_length
        self.generated_query = dspy.Predict(SQL_format)
        self.reasoning = dspy.Predict(Reasoning)
        self.ans = dspy.Predict(Answering)
        self.queries = defaultdict(list)
        self.errors = defaultdict(list)
        self.table = defaultdict(list)
        self.resoning_hist = defaultdict(list)
        self.rm = rm
        
    def forward(self, question, req_cols):

        instructions = "There are no provided for this question"
        
        if type(req_cols) == str:
            columns_to_generate = self.dp_graph.cols(req_cols[2:-2].split("', '"))
        
        try:
            if columns_to_generate:
                    #print("there are column to generate")
                    instructions_lst = self.dp_graph.definitions_s(columns_to_generate)
                    #print(type(instructions))
                    #print(instructions)
                    instructions = ""
                    for instruct in instructions_lst:
                        
                        instructions += " \n" + instruct
                        #print(instruct)
        except:
            pass



        error_hist = ""
        retrieval_str= question + " \n" + instructions
        self.column_description = self.rm.retrieve(retrieval_str, num= 9)# to low for one of the questions, concept_name does not appear in the top 6
        temp_query_hist = []
        try:
            reasoning = self.reasoning(question = question, definitions = instructions, column_description = self.column_description)
        except Exception as e:
            self.errors[question].append(str(e))
            reasoning = "Error generating reasoning: " + str(e)
            return self.ans(question = question, table = reasoning, sql= "Error generating reasoning")
        self.resoning_hist[question].append(reasoning.reasoning.approach)
        # dspy.Suggest(
        #     len(reasoning.reasoning.approach) <= 3000, # change to 1400
        #     "Your reasoning should be fewer than 3000 characters long",
        # )


        try:
            result = self.generated_query(question = question, definitions = instructions,  column_description = self.column_description, approach = reasoning.reasoning.approach)
        except Exception as e:
            self.errors[question].append(str(e))
            result = "Error executing query: " + str(e)
            return self.ans(question = question, table = result, sql= "Error executing query")
        
        query = result.sqlite_query.sql
        temp_query_hist.append(query)
        self.queries[question].append(query)
        conn = self.pool.get_connection() # insted of self.conn.cursor()
        cur = conn.cursor()
        result = ""
        #print(f"From SQL: Query that will be executed: {query}")
        cause_error = True
        dspy.Suggest(
            bool(query in temp_query_hist),
            "Query should be distinct from previous queries that resulted in syntax errors: "+ "; ".join(f"{i+1}) {q}" for i, q in enumerate(temp_query_hist)),
        )
        error_code_fail = ""
        try:
            # add timer here: if cur.execute query takes longer than 5 minutes turn variable overtime to True

            #cur.execute(query)
            timeout= 60 * 5
            output = self.execute_query_with_timeout(self.pool, query, timeout)
            if output is not None:
                print("output", output)
                pass
            else:
                print("query timed out")
                raise Exception("Query execution exceeded the time limit. Use a query that executes faster.")
            
        except Exception as e:
            cause_error = False
            error_code_fail = str(e)
            cur.close()
            self.pool.release_connection(conn)
            self.errors[question].append(str(e))
            #print("Query generator doing error handling")
            
        dspy.Suggest(
            cause_error,
            "Error executing SQLite query " + error_code_fail,
        )
        if len(temp_query_hist) > 3:
            try:
                pred = self.ans(question = question, table = "Error executing query: " + str(e), sql = query)
                return pred
            except Exception as e:
                self.errors[question].append(str(e))
                #print(f"From SQL: number of errors: {len(self.errors[question])}")
                return self.ans(question = question, table = "There was an error during the answering of the question due to the following error: " + str(e), sql = query)
        try:
            #column_names = [description[0] for description in cur.description]
            column_names = [description[0] for description in output[1]]
        except Exception as e:
            self.errors[question].append(str(e))
            return self.ans(question = question, table = "There was an error during the answering of the question due to the following error: " + str(e), sql = query)
        
        header = "|".join(column_names)
        # Initialize result with the header and account for its length.
        result = header
        current_length = len(result)
        #for row in cur.fetchall():
        for row in output[0]:
            row_data = " | ".join([str(cell) for cell in row])
            if current_length + len(row_data) + 1 > self.max_length:
                break  # Keep within the max_length limit.
            result += " \n" + row_data
            current_length += len(row_data) + 1
        self.table[question].append(result)
        cur.close()
        self.pool.release_connection(conn)
        
        try: 
            pred = self.ans(question = question, table = result, sql = query)
        except Exception as e:
            self.errors[question].append(str(e))
            try:
                pred = self.ans(question = question, table = result, sql = query)
            except Exception as e:
                self.errors[question].append(str(e))
                #print(f"From SQL: number of errors: {len(self.errors[question])}")
                return self.ans(question = question, table = "There was an error during the answering of the question due to the following error: " + str(e), sql = query)
        
        #print(f"From SQL: number of errors: {len(self.errors[question])}")
        #print(f"From SQL: result: {pred.answer}, type: {type(pred.answer)}")
        return pred
    def execute_query_with_timeout(self, pool, query, timeout):
        stop_event = threading.Event()
        result_queue = Queue()

        def target():
            conn = pool.get_connection()
            cur = conn.cursor()
            try:
                # Register the progress handler
                def progress_handler():
                    if stop_event.is_set():
                        return 1  # Non-zero value to terminate the query
                    return 0

                conn.set_progress_handler(progress_handler, 1000)  # Call handler every 1000 SQLite instructions

                cur.execute(query)
                results = []
                results.append(cur.fetchall())
                results.append(cur.description)
                result_queue.put(results)
                conn.commit()
                print("Query executed successfully")
            except Exception as e:
                print(f"Query execution failed: {e}")
                result_queue.put(None)
            finally:
                cur.close()
                pool.release_connection(conn)

        thread = threading.Thread(target=target)
        thread.start()

        # Wait for the specified timeout
        thread.join(timeout)

        if thread.is_alive():
            print("Query execution exceeded the time limit.")
            stop_event.set()  # Signal the thread to stop
            thread.join()  # Wait for the thread to finish
            return None

        return result_queue.get()




    def __deepcopy__(self, memo):

        # Create a new instance of the class
        cls = self.__class__
        result = cls.__new__(cls)

        # Copy all attributes except for 'conn'
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            if k == 'pool':
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
        
        result.pool = self.pool
        result.rm = self.rm
        
        return result
    

    def get_history(self):
        return self.queries, self.errors, self.table, self.resoning_hist