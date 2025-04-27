from collections import defaultdict
import copy
import dspy
from pydantic import BaseModel



##MULTI THREAD VERSION AND Better deepcopy

class PM_SQL_multi_simple(dspy.Module):

    def __init__(self, pool, rm, max_length = 1500):
        super().__init__()

        self.pool = pool
        self.max_length = max_length
        self.generated_query = dspy.Predict('column_description, question -> SQLite_query')
        self.ans = dspy.Predict('question, table, sql -> answer')
        self.queries = defaultdict(list)
        self.errors = defaultdict(list)
        self.table = defaultdict(list)
        self.rm = rm
        
    def forward(self, question):
        error_hist = ""
        self.column_description = self.rm.retrieve(question, num= 9)
        temp_query_hist = []
        try:
            result = self.generated_query(question = question, column_description = self.column_description)
        except Exception as e:
            self.errors[question].append(str(e))
            result = "Error executing query: " + str(e)
            return self.ans(question = question, table = result, sql= "Error executing query")
        
        query = result.SQLite_query
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
            cur.execute(query)
            
        except Exception as e:
            cause_error = False
            error_code_fail = str(e)
            cur.close()
            self.pool.release_connection(conn)
            self.errors[question].append(str(e))
            print("Query generator doing error handling")
            
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
                print(f"From SQL: number of errors: {len(self.errors[question])}")
                return self.ans(question = question, table = "There was an error during the answering of the question due to the following error: " + str(e), sql = query)

        column_names = [description[0] for description in cur.description]
        header = "|".join(column_names)
        # Initialize result with the header and account for its length.
        result = header
        current_length = len(result)
        for row in cur.fetchall():
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
                print(f"From SQL: number of errors: {len(self.errors[question])}")
                return self.ans(question = question, table = "There was an error during the answering of the question due to the following error: " + str(e), sql = query)
        
        #print(f"From SQL: number of errors: {len(self.errors[question])}")
        #print(f"From SQL: result: {pred.answer}, type: {type(pred.answer)}")
        return pred
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
        return self.queries, self.errors, self.table