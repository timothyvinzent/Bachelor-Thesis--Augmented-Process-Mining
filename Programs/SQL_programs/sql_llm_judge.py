from collections import defaultdict
import re
import dspy
from pydantic import BaseModel


class scoring(BaseModel):
    score: str
class Assess(dspy.Signature):
    """Assess how closely the Answer matches the prediction in relation to the question. Differences in formating are less important than the actual content. Plausible methods to arrive at the answer are not considered. Only consider the Answer and the Prediction + the Question, nothing else is relevant to you."""
    question = dspy.InputField()
    solution = dspy.InputField()
    prediction = dspy.InputField()
    reasoning = dspy.OutputField(desc="Reasoning behind the score")
    score = dspy.OutputField(desc="0 means its absolutely wrong, 1 means that the prediction answers parts of the question but not all of it, 2 means its an exact match in terms of content")


class LM_EVAL(dspy.Module):

    def __init__(self, gpt4T):
        super().__init__()
        self.gpt4T = gpt4T
        self.reasoning = defaultdict(list)
        self.scorer = dspy.Predict(Assess)
        self.hist = []

    def forward(self, example, prediction, trace= None):
        question = example.question
        example = example.example
        pred = prediction.answer
        with dspy.context(lm=self.gpt4T):        
            pred = self.scorer(question=question, solution=example, prediction=pred)
        self.reasoning[question].append(pred.reasoning)                
        try:
        
            numbers = re.findall(r'\d+', pred.score)
        except:
            pass
        
        # Check if we found any numbers and take the last one
        if numbers:
            last_number = numbers[-1]
            
            # Convert the last found number to an integer and check if it's in the valid range
            last_number_int = int(last_number)
            if last_number_int in {0, 1, 2}:
                pred.score = last_number_int #str(last_number_int) this is used for the compiling of the judge
                #print(f"From LM_EVAL: {pred.score}, type: {type(pred.score)}, after assigning value to it")
                if trace is None:
                    self.hist.append(pred.score)
                    return pred.score 
                    
                else:
                    print("trace is being used")
                    boolean = pred.score == 2
                    pred.score = boolean
                    self.hist.append(pred.score)
                    return pred.score
            else:
                if trace is None:
                
                    return 0
                else:
                
                    return False
        else:
            if trace is None:
                self.hist.append(0)
                return 0
            else:
                self.hist.append(False)
                return False
            #print(f"From LM_EVAL: {pred.answer},type: {type(pred.answer)} did not take a single number as output")
            
    

    def get_reasoning(self):
        return self.reasoning
    def get_history(self):
        return self.hist

