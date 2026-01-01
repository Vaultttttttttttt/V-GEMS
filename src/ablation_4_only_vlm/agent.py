import json
from typing import Dict, Iterator, List, Literal, Optional, Tuple, Union

from qwen_agent.agents.fncall_agent import FnCallAgent
from qwen_agent.llm import BaseChatModel
from qwen_agent.llm.schema import ASSISTANT, DEFAULT_SYSTEM_MESSAGE, Message
from qwen_agent.settings import MAX_LLM_CALL_PER_RUN
from qwen_agent.tools import BaseTool
from qwen_agent.utils.utils import format_as_text_message, merge_generate_cfgs
from openai import OpenAI
import time
from prompts import *


TOOL_DESC = (
    '{name_for_model}: Call this tool to interact with the {name_for_human} API. '
    'What is the {name_for_human} API useful for? {description_for_model} Parameters: {parameters} {args_format}')

class VGems(FnCallAgent):
    """This explorer agent use ReAct format to call tools"""

    def __init__(self,
                 function_list: Optional[List[Union[str, Dict, BaseTool]]] = None,
                 llm: Optional[Union[Dict, BaseChatModel]] = None,
                 system_message: Optional[str] = DEFAULT_SYSTEM_MESSAGE,
                 name: Optional[str] = None,
                 description: Optional[str] = None,
                 files: Optional[List[str]] = None,
                 **kwargs):
        super().__init__(function_list=function_list,
                         llm=llm,
                         system_message=system_message,
                         name=name,
                         description=description,
                         files=files,
                         **kwargs)
        self.extra_generate_cfg = merge_generate_cfgs(
            base_generate_cfg=self.extra_generate_cfg,
            new_generate_cfg={'stop': ['Observation:', 'Observation:\n']},
        )
        self.client = OpenAI(
            api_key=llm['api_key'], 
            base_url=llm['model_server'],
        )
        self.llm_cfg = llm
        self.momery = []

    def observation_information_extraction(self, query, observation):
        user_prompt = "- Query: {query}\n- Observation: {observation}".format(query=query, observation=observation)
        messages = [
            {'role': 'system', 'content': STSTEM_CRITIIC_INFORMATION},
            {'role': 'user', 'content':  user_prompt}]
        max_retries = 10
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.llm_cfg['model'],
                    response_format={"type": "json_object"},
                    messages=messages
                )
                print(response.choices[0].message.content)
                # response_content = json.loads(response.choices[0].message.content)
                if "true" in response.choices[0].message.content:
                    try:
                        return json.loads(response.choices[0].message.content)["information"]
                    except:
                        return response.choices[0].message.content
                else:
                    return None
            except Exception as e:
                print(e)
                if attempt < max_retries - 1:
                    time.sleep(1 * (2 ** attempt))  # Exponential backoff
                else:
                    raise e  # Raise the exception if the last retry fails

    def critic_information(self, query, memory):
        memory_text = "\n---\n".join(memory) if memory else "No information collected yet"
        memory_count = len(memory)

        # Let LLM analyze the query itself to determine requirements
        user_prompt = f"""- Query: {query}
- Accumulated Information:
{memory_text}

- Items collected: {memory_count}

Based on the criteria in the system prompt, evaluate if this information is sufficient to answer the query.
You need to:
1. Analyze the query to determine if it asks for a SPECIFIC NUMBER of items (e.g., "找5篇文章", "give me 10 articles") or just asks a QUESTION (e.g., "What is the deadline?")
2. If the query asks for N items, check if we have collected at least 50% of N items
3. If the query asks a question, check if the accumulated information provides a complete answer
4. Make your judgment based on the above analysis"""

        messages = [
            {'role': 'system', 'content': STSTEM_CRITIIC_ANSWER},
            {'role': 'user', 'content': user_prompt}]

        max_retries = 10
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.llm_cfg['model'],
                    response_format={"type": "json_object"},
                    messages=messages
                )
                result = response.choices[0].message.content
                print(f"[critic_information] {result}")

                result_json = json.loads(result)

                # Check if judge is true
                if result_json.get("judge") == True or "true" in result.lower():
                    answer = result_json.get("answer")
                    if answer:
                        return answer
                    else:
                        # If judge is true but no answer field, return the whole response
                        return result
                else:
                    # judge is false, return None
                    reason = result_json.get("reason", "Not enough information")
                    print(f"[critic_information] Judge=false, reason: {reason}")
                    return None

            except Exception as e:
                print(f"[critic_information] Error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1 * (2 ** attempt))  # Exponential backoff
                else:
                    print(f"[critic_information] All retries failed, returning None")
                    return None

    def _run(self, messages: List[Message], lang: Literal['en', 'zh'] = 'en', **kwargs) -> Iterator[List[Message]]:
        text_messages = self._prepend_react_prompt(messages, lang=lang)
        num_llm_calls_available = MAX_LLM_CALL_PER_RUN
        response: str = 'Thought: '
        query = self.llm_cfg["query"]
        action_count = self.llm_cfg.get("action_count", MAX_LLM_CALL_PER_RUN)
        num_llm_calls_available = action_count

        # Track visited URLs and consecutive no-action cases
        visited_urls = set()
        consecutive_no_action = 0
        consecutive_no_useful_info = 0

        while num_llm_calls_available > 0:
            num_llm_calls_available -= 1

            # Check if we should force end (running out of actions but have some results)
            if num_llm_calls_available < action_count * 0.15 and len(self.momery) > 0:
                print(f"[INFO] Running low on actions ({num_llm_calls_available} left), attempting to generate final answer...")
                stage2 = self.critic_information(query, self.momery)
                if stage2:
                    response = f'Final Answer: {stage2}'
                    yield [Message(role=ASSISTANT, content=response)]
                    break
                else:
                    # Critic says not enough, give a clear warning but let Agent continue if it still has steps
                    print(f"[WARNING] Critic says information is insufficient but we're running low on steps. Agent will continue exploring if possible.")
                    # Don't force output here - let the agent try to find more information

            output = []
            for output in self._call_llm(messages=text_messages):
                pass  # Accumulate all streaming outputs

            # Yield the complete output once after streaming finishes
            if output:
                yield [Message(role=ASSISTANT, content=output[-1].content)]
                response += output[-1].content

            has_action, action, action_input, thought = self._detect_tool("\n"+output[-1].content)
            if not has_action:
                consecutive_no_action += 1
                print(f"[WARNING] No action detected (count: {consecutive_no_action})")

                if "Final Answer: " in output[-1].content:
                    break

                # Force break if stuck in no-action loop
                if consecutive_no_action >= 3:
                    print(f"[ERROR] LLM stuck in no-action loop for {consecutive_no_action} times, forcing final answer")
                    if len(self.momery) > 0:
                        # Try critic first
                        stage2 = self.critic_information(query, self.momery)
                        if stage2:
                            yield [Message(role=ASSISTANT, content=f'Final Answer: {stage2}')]
                        else:
                            # Critic says not enough - give honest partial answer
                            answer = f"抱歉，Agent 遇到问题无法继续。以下是已收集的 {len(self.momery)} 条信息：\n\n" + "\n---\n".join(self.momery)
                            yield [Message(role=ASSISTANT, content=f'Final Answer: {answer}')]
                    else:
                        yield [Message(role=ASSISTANT, content='Final Answer: 抱歉，未能找到相关信息。')]
                    break

                # Provide helpful hint to LLM
                hint = "\nObservation: [系统提示] 你的上一步没有执行有效的action。"
                if len(self.momery) > 0:
                    hint += f" 当前已找到 {len(self.momery)} 条信息。请回顾query要求，判断信息是否充足。如果充足，请给出最终答案(Final Answer)；否则继续探索其他页面。"
                else:
                    hint += " 请使用正确的Action格式继续探索。记住你可以使用的工具有：visit_page（点击按钮）。"
                hint += " 请务必输出 Action 和 Action Input！"
                hint += "\nThought: "
                text_messages[-1].content += hint
                response += hint
                continue
            else:
                consecutive_no_action = 0  # Reset counter

            # Add the tool result
            query = self.llm_cfg["query"]
            observation = self._call_tool(action, action_input, messages=messages, **kwargs)

            # Check for URL duplication - extract real URL from observation
            current_url = None
            import re
            url_match = re.search(r'The url now is (https?://[^\s\n]+)', observation)
            if url_match:
                current_url = url_match.group(1).strip()
                print(f"[DEBUG] Extracted URL from observation: {current_url}")

            if current_url and current_url in visited_urls:
                consecutive_no_useful_info += 1
                print(f"[WARNING] Revisiting URL: {current_url} (count: {consecutive_no_useful_info})")

                # Force back navigation if stuck revisiting
                if consecutive_no_useful_info >= 3:
                    hint = f"\n[系统警告] 你已连续 {consecutive_no_useful_info} 次访问重复页面！访问完全不同的新页面。"
                    consecutive_no_useful_info = 0
                else:
                    hint = f"\n[提示] URL '{current_url}' 已访问过，建议尝试其他页面或返回上级页面。"

                observation += hint

            if current_url:
                visited_urls.add(current_url)

            stage1 = self.observation_information_extraction(query, observation)
            if stage1:
                consecutive_no_useful_info = 0
                self.momery.append(stage1+"\n")
                if len(self.momery) > 1:
                    yield [Message(role=ASSISTANT, content= "Memory:\n" + "-".join(self.momery)+"\"}")]
                else:
                    yield [Message(role=ASSISTANT, content= "Memory:\n" + "-" + self.momery[0]+"\"}")]

                # CRITICAL: Force Agent to check progress after finding info
                progress_hint = f"\n[SYSTEM ALERT] You found useful information! Current count: {len(self.momery)}. Review the query to determine if you need more information or can provide the Final Answer now."
                print(progress_hint)

                stage2 = self.critic_information(query, self.momery)
                if stage2:
                    response = f'Final Answer: {stage2}'
                    yield [Message(role=ASSISTANT, content=response)]
                    break
            else:
                consecutive_no_useful_info += 1
                print(f"[INFO] No useful info from current page (count: {consecutive_no_useful_info})")

                # Add feedback when no useful info
                feedback = f" [提示: 当前页面无新信息({consecutive_no_useful_info}次)。已收集{len(self.momery)}条信息。"
                if consecutive_no_useful_info >= 2:
                    feedback += "尝试其他页面。"
                feedback += "]"
                observation = observation + feedback

            observation = f'\nObservation: {observation}\nThought: '
            response += observation
            # yield [Message(role=ASSISTANT, content=response)]

            if (not text_messages[-1].content.endswith('\nThought: ')) and (not thought.startswith('\n')):
                # Add the '\n' between '\nQuestion:' and the first 'Thought:'
                text_messages[-1].content += '\n'
            if action_input.startswith('```'):
                # Add a newline for proper markdown rendering of code
                action_input = '\n' + action_input
            text_messages[-1].content += thought + f'\nAction: {action}\nAction Input: {action_input}' + observation
            # print(text_messages[-1].content)

    def _prepend_react_prompt(self, messages: List[Message], lang: Literal['en', 'zh']) -> List[Message]:
        tool_descs = []
        for f in self.function_map.values():
            function = f.function
            name = function.get('name', None)
            name_for_human = function.get('name_for_human', name)
            name_for_model = function.get('name_for_model', name)
            assert name_for_human and name_for_model
            args_format = function.get('args_format', '')
            tool_descs.append(
                TOOL_DESC.format(name_for_human=name_for_human,
                                 name_for_model=name_for_model,
                                 description_for_model=function['description'],
                                 parameters=json.dumps(function['parameters'], ensure_ascii=False),
                                 args_format=args_format).rstrip())
        tool_descs = '\n\n'.join(tool_descs)
        tool_names = ','.join(tool.name for tool in self.function_map.values())
        text_messages = [format_as_text_message(m, add_upload_info=True, lang=lang) for m in messages]
        text_messages[-1].content = SYSTEM_EXPLORER.format(
            tool_descs=tool_descs,
            tool_names=tool_names,
            query=text_messages[-1].content,
        )
        return text_messages

    def _detect_tool(self, text: str) -> Tuple[bool, str, str, str]:
        special_func_token = '\nAction:'
        special_args_token = '\nAction Input:'
        special_obs_token = '\nObservation:'
        func_name, func_args = None, None
        i = text.rfind(special_func_token)
        j = text.rfind(special_args_token)
        k = text.rfind(special_obs_token)
        if 0 <= i < j:  # If the text has `Action` and `Action input`,
            if k < j:  # but does not contain `Observation`,
                # then it is likely that `Observation` is ommited by the LLM,
                # because the output text may have discarded the stop word.
                text = text.rstrip() + special_obs_token  # Add it back.
            k = text.rfind(special_obs_token)
            func_name = text[i + len(special_func_token):j].strip()
            func_args = text[j + len(special_args_token):k].strip()
            text = text[:i]  # Return the response before tool call, i.e., `Thought`
        return (func_name is not None), func_name, func_args, text
