import streamlit as st
import os
import json5
from agent import VGems
from qwen_agent.tools.base import BaseTool, register_tool
import os
import re
import json
import asyncio
from utils import *
import base64
from PIL import Image
from bs4 import BeautifulSoup
from openai import OpenAI
import time
path = 'count.txt'


if 'DASHSCOPE_API_KEY' not in os.environ and 'OPENAI_API_KEY' not in os.environ:
    raise ValueError("Please set the environment variable 'DASHSCOPE_API_KEY' or 'OPENAI_API_KEY' to your API key.")
if 'DASHSCOPE_API_KEY' in os.environ:
    model = "qwen-plus"
    llm_cfg = {
        'model': model,
        'api_key': os.getenv('DASHSCOPE_API_KEY'),
        'model_server': "https://dashscope.aliyuncs.com/compatible-mode/v1" ,
        'generate_cfg': {
                'top_p': 0.8,
                'max_input_tokens': 120000,
                'max_retries': 20
        },
    }
if 'OPENAI_API_KEY' in os.environ and 'OPENAI_MODEL_SERVER' in os.environ:
    llm_cfg = {
        'model': 'qwen3-coder-plus',
        'api_key': 'sk-e543e83d6c394411b3343369aa9027a2',
        'model_server': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        'generate_cfg': {
                'top_p': 0.8,
                'max_input_tokens': 120000,
                'max_retries': 20
        },
    }

def save_screenshot_info(screenshot_path, url):
    """
    Save current screenshot information to a JSON file for VLM access

    Args:
        screenshot_path (str): Path to the screenshot file
        url (str): URL of the page
    """
    import time
    try:
        with open("current_screenshot.json", "w") as f:
            json.dump({
                "screenshot_path": screenshot_path,
                "url": url,
                "timestamp": time.time()
            }, f)
    except Exception as e:
        print(f"Failed to save screenshot info: {e}")

def extract_links_with_text(html, current_url):
    """
    Extract links with text from HTML, intelligently capturing context for generic button names.

    Args:
        html (str): html content
        current_url (str): current page URL (for resolving relative paths)

    Returns:
        str: clickable buttons
    """
    with open("ROOT_URL.txt", "r") as f:
        ROOT_URL = f.read()
    soup = BeautifulSoup(html, 'html.parser')
    links = []

    # Generic words that need context
    generic_words = {
        '查看更多', '更多', 'more', 'More', 'MORE', '详情', '点击进入',
        'More »', '>>', '...', '››', '»', '→', '进入', '查看',
        '了解更多', 'Learn More', 'Read More', 'View More', 'See More',
        '查看详情', 'Details', 'View Details', '>', '»»', '>>|'
    }

    def find_context_for_link(a_tag):
        """
        Find meaningful context for a link, especially for generic button text.
        Returns the enhanced text with context if found.
        """
        # Try to get text from title or aria-label first
        text = a_tag.get('title') or a_tag.get('aria-label') or ''.join(a_tag.stripped_strings)

        # If text is empty or generic, try to find context
        if not text or text.strip() in generic_words:
            original_text = text or '更多'
            context = None

            # Method 1: Look for previous sibling elements (like <span>科研动态</span>)
            prev_sibling = a_tag.find_previous_sibling(['span', 'h1', 'h2', 'h3', 'h4', 'h5', 'div', 'p', 'strong', 'b'])
            if prev_sibling:
                context_text = ''.join(prev_sibling.stripped_strings).strip()
                if context_text and len(context_text) < 50:  # Avoid too long context
                    context = context_text

            # Method 2: Look for parent element with title/heading
            if not context:
                parent = a_tag.find_parent(['div', 'li', 'section', 'article', 'td'])
                if parent:
                    # Look for title-like elements in parent
                    title_elem = parent.find(['h1', 'h2', 'h3', 'h4', 'h5', 'span', 'div', 'p'],
                                             class_=re.compile(r'title|header|heading|name', re.I))
                    if title_elem and title_elem != a_tag:
                        context_text = ''.join(title_elem.stripped_strings).strip()
                        if context_text and len(context_text) < 50:
                            context = context_text

            # Method 3: Look for nearby text nodes
            if not context:
                # Get all text in parent, excluding the link itself
                parent = a_tag.find_parent(['div', 'li', 'td'])
                if parent:
                    # Get text before the link
                    for elem in parent.children:
                        if elem == a_tag:
                            break
                        if hasattr(elem, 'stripped_strings'):
                            nearby_text = ''.join(elem.stripped_strings).strip()
                            if nearby_text and len(nearby_text) < 50:
                                context = nearby_text
                                break

            # Combine context with original text
            if context:
                # Remove common suffixes from context
                context = context.rstrip('：:')
                text = f"{context} - {original_text}"
            elif not text:
                text = original_text

        return text.strip() if text else None

    # Extract <a> tags with href
    for a_tag in soup.find_all('a', href=True):
        url = a_tag['href']
        text = find_context_for_link(a_tag)

        if text and "javascript" not in url and not url.endswith(('.jpg', '.png', '.gif', '.jpeg', '.pdf')):
            # Use current_url to resolve relative paths correctly
            full_url = process_url(current_url, url)
            # Check if the resolved URL is within the same domain
            if full_url.startswith(ROOT_URL):
                links.append({'url': full_url, 'text': text})

    # Extract <a> tags with onclick
    for a_tag in soup.find_all('a', onclick=True):
        onclick_text = a_tag['onclick']
        text = find_context_for_link(a_tag)

        match = re.search(r"window\.location\.href='([^']*)'", onclick_text)
        if match:
            url = match.group(1)
            if url and text and not url.endswith(('.jpg', '.png', '.gif', '.jpeg', '.pdf')):
                full_url = process_url(current_url, url)
                if full_url.startswith(ROOT_URL):
                    links.append({'url': full_url, 'text': text})

    # Extract <a> tags with data-url
    for a_tag in soup.find_all('a', attrs={'data-url': True}):
        url = a_tag['data-url']
        text = find_context_for_link(a_tag)
        if url and text and not url.endswith(('.jpg', '.png', '.gif', '.jpeg', '.pdf')):
            full_url = process_url(current_url, url)
            if full_url.startswith(ROOT_URL):
                links.append({'url': full_url, 'text': text})

    # Extract <a> tags with herf-mask class
    for a_tag in soup.find_all('a', class_='herf-mask'):
        url = a_tag.get('href')
        text = find_context_for_link(a_tag)
        if url and text and not url.endswith(('.jpg', '.png', '.gif', '.jpeg', '.pdf')):
            full_url = process_url(current_url, url)
            if full_url.startswith(ROOT_URL):
                links.append({'url': full_url, 'text': text})

    # Extract <button> tags with onclick
    for button in soup.find_all('button', onclick=True):
        onclick_text = button['onclick']
        text = button.get('title') or button.get('aria-label') or ''.join(button.stripped_strings)
        match = re.search(r"window\.location\.href='([^']*)'", onclick_text)
        if match:
            url = match.group(1)
            if url and text:
                full_url = process_url(current_url, url)
                if full_url.startswith(ROOT_URL):
                    links.append({'url': full_url, 'text': text})

    # Remove duplicates - prefer buttons with context over generic ones
    unique_links = {}
    for item in links:
        key = item['url']
        # If this URL already exists, keep the one with more descriptive text
        if key in unique_links:
            existing_text = unique_links[key]['text']
            new_text = item['text']
            # Prefer text with context (contains ' - ')
            if ' - ' in new_text and ' - ' not in existing_text:
                unique_links[key] = item
            elif len(new_text) > len(existing_text):
                unique_links[key] = item
        else:
            unique_links[key] = item

    # Save to BUTTON_URL_ADIC.json
    if not os.path.exists("BUTTON_URL_ADIC.json"):
        with open("BUTTON_URL_ADIC.json", "w") as f:
            json.dump({}, f)
    with open("BUTTON_URL_ADIC.json", "r") as f:
        BUTTON_URL_ADIC = json.load(f)
    for temp in list(unique_links.values()):
        BUTTON_URL_ADIC[temp["text"]] = temp["url"]
    with open("BUTTON_URL_ADIC.json", "w") as f:
        json.dump(BUTTON_URL_ADIC, f, ensure_ascii=False, indent=2)

    # Format output
    info = ""
    for i in list(unique_links.values()):
        info += "<button>" + i["text"] + "<button>" + "\n"
    return info

if __name__ == "__main__":
    with open(path, "w") as f:
        f.write("0")
        
    st.title('🤝VGems')
    st.markdown("### 📚Introduction")
    st.markdown("👋Welcome to VGems! VGems is a web-based conversational agent that can help you navigate websites and find information.")
    st.markdown("📑The paper of VGems is available at [arXiv]().")
    st.markdown("✨You can bulid your own VGems by following the [instruction](https://github.com/Alibaba-NLP/VGems).")
    st.markdown("🙋If you have any questions, please feel free to contact us via the [Github issue](https://github.com/Alibaba-NLP/VGems/issue).")
    st.markdown("### 🚀Let's start exploring the website!")
    if 'form_1_text' not in st.session_state:
        st.session_state.form_1_text = ""
    if 'form_2_text' not in st.session_state:
        st.session_state.form_2_text = ""

    with st.sidebar:
        MAX_ROUNDS = st.number_input('最大步数：', min_value=1, max_value=150, value=100, step=1)
        website_example = st.sidebar.selectbox('示例网站：', ['https://www.chinadaily.com.cn/','https://m.news.cn/','https://www.163.com'])
        question_example = st.sidebar.selectbox('示例问题：', ["帮我找2篇与ai和教育相关的文章，并把它们的url返回给我。注意你必须保证给我的url能正确打开出来文章，如果不能的话继续去找，不能糊弄我。所以对于你检测到的url你必须下一步点进去检查才能给我",'''帮我找5篇与ai相关的文章，并把它们的url返回给我。注意你必须保证给我的url能正确打开出来文章，如果不能的话继续去找，不能糊弄我。所以对于你检测到的url你必须下一步点进去检查才能给我。url的返回格式为json：
                                                                {
                                                                    urls:[
                                                                        url1,
                                                                        url2,
                                                                        ...
                                                                    ]
                                                                }'''])

    col1, col2 = st.columns([3, 1]) 
    with col1:
        with st.form(key='my_form'):
            form_1_text = st.text_area("**🤯Memory**", value="No Memory", height=68)
            website = st.text_area('👉Website', value=website_example, placeholder='Input the website you want to walk through.')
            query = st.text_area('🤔Query', value=question_example, placeholder='Input the query you want to ask.')
            submit_button = st.form_submit_button('Start!!!!')
            
            if submit_button:
                if website and query:
                    tools = ["visit_page", "count_usefulness", "query_requirement", "calculate_understanding_score", "use_vlm_analysis"]
                    llm_cfg["query"] = query
                    llm_cfg["action_count"] = MAX_ROUNDS
                    bot = VGems(llm=llm_cfg,
                        function_list=tools
                        )
                    bot._call_tool('query_requirement', action_input=json.dumps({"op": "set", "query": query}, ensure_ascii=False))

                    # Clear BUTTON_URL_ADIC.json for new session to avoid cross-session contamination
                    BUTTON_URL_ADIC = {}
                    with open("BUTTON_URL_ADIC.json", "w") as f:
                        json.dump({}, f)

                    # Initialize navigation step counter
                    with open("navigation_steps.txt", "w") as f:
                        f.write("0")

                    ROOT_URL = website
                    with open("ROOT_URL.txt", "w") as f:
                        f.write(ROOT_URL)
                    messages = []  # This stores the chat history.
                    visited_links = []
                    start_prompt = """query:
{query}

official website:
{website}

IMPORTANT INITIAL STEPS (YOU MUST FOLLOW):
1. First, evaluate the starting page understanding score:
   Action: calculate_understanding_score
   Action Input: {{"observation": "<content from Observation below>", "query": "{query}", "url": "{website}"}}

3. Then proceed with your exploration based on the score.
""".format(query=query, website=website)
                    st.markdown('**🌐Now visit**')
                    st.write(website)
                    html, markdown, screenshot = asyncio.run(get_info(website))
                    with col2:
                        st.markdown('**📸Observation**')
                        if screenshot:
                            st.session_state.image_index = 0
                            print("get screenshot!")
                            image_folder = "images/"
                            if not os.path.exists(image_folder):
                                os.makedirs(image_folder)
                            with open(image_folder+str(st.session_state.image_index)+".png", "wb") as f:
                                f.write(base64.b64decode(screenshot))
                            image_files = os.listdir(image_folder)
                            image_files = [f for f in image_files if f.endswith(('.png', '.jpg', '.jpeg'))]
                            image_path = os.path.join(image_folder, image_files[st.session_state.image_index])
                            image = Image.open(image_folder+str(st.session_state.image_index)+".png")
                            st.image(image, caption='Start Obervation', width=400)
                        
                    buttons = extract_links_with_text(html, website)
                    response = "website information:\n\n" + markdown + "\n\n"
                    response += "clickable button:\n\n" + buttons + "\n\nEach button is wrapped in a <button> tag"
                    start_prompt += "\nObservation:" + response + "\n\n"
                    messages.append({'role': 'user', 'content':start_prompt})
                    cnt = 0
                    response = []
                    response = bot.run(messages=messages, lang = "zh")
                    for i in response:
                        if "\"}" in i[0]["content"] and "Memory" not in i[0]["content"]:
                            st.markdown('**💭Thoughts**')
                            st.markdown(i[0]["content"].split("Action")[0])
                        elif "\"}" in i[0]["content"] and "Memory" in i[0]["content"]:
                            st.text_area('**🤯Memory Update**', i[0]["content"][:-2])
                        if "Final Answer" in i[0]["content"]:
                            st.session_state.answer = i[0]["content"]

                            # Read navigation steps
                            try:
                                with open("navigation_steps.txt", "r") as f:
                                    nav_steps = int(f.read().strip() or "0")
                            except:
                                nav_steps = 0

                            st.markdown('**🙋Answer**')
                            st.write(st.session_state.answer)
                            st.markdown(f'**📊Navigation Steps**: {nav_steps} button clicks')

                            # Save answer to file
                            try:
                                import datetime
                                answer_data = {
                                    "timestamp": datetime.datetime.now().isoformat(),
                                    "query": query,
                                    "website": website,
                                    "answer": st.session_state.answer,
                                    "memory_count": len(bot.momery) if hasattr(bot, 'momery') else 0
                                }

                                # Append to answers history file
                                answers_file = "answers_history.json"
                                history = []
                                if os.path.exists(answers_file):
                                    with open(answers_file, "r", encoding="utf-8") as f:
                                        history = json.load(f)

                                history.append(answer_data)

                                with open(answers_file, "w", encoding="utf-8") as f:
                                    json.dump(history, f, ensure_ascii=False, indent=2)

                                st.success(f"✅ Answer saved to {answers_file}")
                            except Exception as e:
                                st.warning(f"⚠️ Failed to save answer: {e}")
                else:
                    st.error('Please input the website and query.')


@register_tool('visit_page',allow_overwrite=True)
class VisitPage(BaseTool):
    """
    description: A tool that visits a webpage and extracts the content of the page.
    parameters:
        - name: url
            type: string
            description: The URL of the webpage to visit.
            required: true
    """
    description = 'A tool analyzes the content of a webpage and extracts buttons associated with sublinks. Simply input the button which you want to explore, and the tool will return both the markdown-formatted content of the corresponding page of button and a list of new clickable buttons found on the new page.'
    parameters = [{
        'name': 'button',
        'type': 'string',
        'description': 'the button you want to click',
        'required': True
    }]

            
    def call(self, params: str, **kwargs) -> str:
        if not params.strip().endswith("}"):
            if "}" in params.strip():
                params = "{" + get_content_between_a_b("{","}",params) + "}"
            else:
                if not params.strip().endswith("\""):
                    params = params.strip() + "\"}"
                else:
                    params = params.strip() + "}"
        params = "{" + get_content_between_a_b("{","}",params) + "}"
        if 'button' in json5.loads(params):
            with open("BUTTON_URL_ADIC.json", "r") as f:
                BUTTON_URL_ADIC = json.load(f)
            if json5.loads(params)['button'].replace("<button>","") in BUTTON_URL_ADIC:
                # Increment navigation step counter
                try:
                    with open("navigation_steps.txt", "r") as f:
                        steps = int(f.read().strip() or "0")
                    with open("navigation_steps.txt", "w") as f:
                        f.write(str(steps + 1))
                except:
                    with open("navigation_steps.txt", "w") as f:
                        f.write("1")

                st.markdown('**👆Click Button**')
                st.write(json5.loads(params)['button'].replace("<button>",""))
                url = BUTTON_URL_ADIC[json5.loads(params)['button'].replace("<button>","")]
                html, markdown, screenshot = asyncio.run(get_info(url))
                st.markdown('**🌐Now Visit**')
                st.write(url)
                with col2:
                    st.write("")
                    st.markdown('**📸Observation**')
                    if screenshot:
                        print("get screenshot!")
                        image_folder = "images/"
                        image_path = image_folder+str(st.session_state.image_index+1)+".png"
                        with open(image_path, "wb") as f:
                            f.write(base64.b64decode(screenshot))
                        st.session_state.image_index += 1
                        save_screenshot_info(image_path, url)
                        image = Image.open(image_folder+str(st.session_state.image_index)+".png")
                        st.image(image, caption='Step ' + str(st.session_state.image_index) + ' Obervation', width=400)
                response_bottons = extract_links_with_text(html, url)
                response_content = markdown

                # Read all discovered buttons from BUTTON_URL_ADIC for global view
                try:
                    with open("BUTTON_URL_ADIC.json", "r") as f:
                        all_discovered_buttons = json.load(f)
                    all_button_names = list(all_discovered_buttons.keys())

                    # Build enhanced response
                    if response_content:
                        response = f"The url now is {url}.\n\n"
                        response += "=== CURRENT PAGE ===\n"
                        response += f"Website information:\n{response_content}\n\n"
                        response += f"Clickable buttons on THIS page:\n{response_bottons}\n\n"
                        response += "=== GLOBAL DISCOVERY ===\n"
                        response += f"All discovered buttons (from all visited pages): {', '.join(all_button_names[:30])}"
                        if len(all_button_names) > 30:
                            response += f" ... and {len(all_button_names) - 30} more"
                        response += "\nYou can visit ANY of these discovered buttons using visit_page action.\n\n"
                        response += "💡 STRATEGY: Breadth-first is more efficient - explore sibling pages at current level before going deeper.\n"
                    else:
                        response = f"The url now is {url}.\n\n The information of the current page is not accessible\n\n"
                        response += "Clickable buttons are wrapped in <button> tag" + response_bottons
                except Exception as e:
                    print(f"[WARNING] Failed to read BUTTON_URL_ADIC: {e}")
                    if response_content:
                        response = f"The url now is {url}.\n\n The web informtaion if:\n\n" + response_content + "\n\n"
                    else:
                        response = f"The url now is {url}.\n\n The information of the current page is not accessible\n\n"
                    response += "Clickable buttons are wrapped in <button> tag" + response_bottons

                return response
            else:
                return "The button can not be clicked, please retry a new botton!"
        else:
            return "Your input is invalid, plase output the action input correctly!"

@register_tool('visit_url', allow_overwrite=True)
class VisitUrl(BaseTool):
    """
    description: Directly visit a specified URL within the same root domain and return the page content and clickable buttons.
    parameters:
        - name: url
            type: string
            description: The absolute URL to visit. Must belong to the ROOT_URL domain.
            required: true
    """
    description = 'Directly visit a specified URL within the same root domain and return the page content and clickable buttons.'
    parameters = [{
        'name': 'url',
        'type': 'string',
        'description': 'The absolute URL to visit. Must belong to the ROOT_URL domain.',
        'required': True
    }]

    def call(self, params: str, **kwargs) -> str:
        if not params.strip().endswith("}"):
            if "}" in params.strip():
                params = "{" + get_content_between_a_b("{","}",params) + "}"
            else:
                if not params.strip().endswith("\""):
                    params = params.strip() + "\"}"
                else:
                    params = params.strip() + "}"
        params = "{" + get_content_between_a_b("{","}",params) + "}"

        try:
            data = json5.loads(params)
        except Exception:
            return "invalid params"

        url = str(data.get('url', '')).strip()
        if not url:
            return "invalid params: missing url"

        try:
            with open("ROOT_URL.txt", "r") as f:
                ROOT_URL = f.read().strip()
        except Exception:
            ROOT_URL = ""

        # Domain guard: only allow same-origin visits if ROOT_URL is set
        if ROOT_URL and not process_url(ROOT_URL, url).startswith(ROOT_URL):
            return "invalid url: out of ROOT_URL domain"

        # Increment navigation step counter
        try:
            with open("navigation_steps.txt", "r") as f:
                steps = int(f.read().strip() or "0")
            with open("navigation_steps.txt", "w") as f:
                f.write(str(steps + 1))
        except:
            with open("navigation_steps.txt", "w") as f:
                f.write("1")

        try:
            html, markdown, screenshot = asyncio.run(get_info(url))
        except Exception:
            return "failed to fetch url"

        response_buttons = extract_links_with_text(html, url)
        response_content = markdown

        # Read all discovered buttons from BUTTON_URL_ADIC
        try:
            with open("BUTTON_URL_ADIC.json", "r") as f:
                all_discovered_buttons = json.load(f)
            all_button_names = list(all_discovered_buttons.keys())

            # Build enhanced response with global view
            response = f"The url now is {url}.\n\n"
            response += "=== CURRENT PAGE ===\n"
            response += f"Website information:\n{response_content}\n\n"
            response += f"Clickable buttons on THIS page:\n{response_buttons}\n\n"
            response += "=== GLOBAL DISCOVERY ===\n"
            response += f"All discovered buttons (from all visited pages): {', '.join(all_button_names[:30])}"
            if len(all_button_names) > 30:
                response += f" ... and {len(all_button_names) - 30} more"
            response += "\nYou can visit ANY of these discovered buttons using visit_page action.\n\n"
            response += "💡 STRATEGY: Breadth-first is more efficient - explore sibling pages at current level before going deeper.\n"
        except Exception as e:
            print(f"[WARNING] Failed to read BUTTON_URL_ADIC: {e}")
            response = f"The url now is {url}.\n\n The information of the current page:\n\n{response_content}\n\n"
            response += "Clickable buttons are wrapped in <button> tag" + response_buttons

        with st.container():
            st.markdown('**🌐Now Visit**')
            st.write(url)
        if screenshot:
            with st.container():
                st.markdown('**📸Observation**')
            try:
                image_folder = "images/"
                if not os.path.exists(image_folder):
                    os.makedirs(image_folder)
                idx = getattr(st.session_state, 'image_index', 0) + 1
                image_path = image_folder+str(idx)+".png"
                with open(image_path, "wb") as f:
                    f.write(base64.b64decode(screenshot))
                st.session_state.image_index = idx
                save_screenshot_info(image_path, url)
                image = Image.open(image_folder+str(idx)+".png")
                st.image(image, caption='VisitUrl Step ' + str(idx) + ' Observation', width=400)
            except Exception:
                pass

        # Return the response we built earlier (already includes global discovery)
        return response

@register_tool('url_stack', allow_overwrite=True)
class UrlStack(BaseTool):
    """
    description: Manage a simple URL stack for navigation. Persisted in nav_chain.json.
    parameters:
        - name: op
            type: string
            description: Operation to perform. One of [init, push, back, peek, parent, get, reset].
            required: true
        - name: url
            type: string
            description: Required for push/init. The URL to set or append.
            required: false
        - name: steps
            type: integer
            description: For back: the number of levels to go back (default 1).
            required: false
    """
    description = 'Manage a simple URL stack for navigation. Persisted in nav_chain.json.'
    parameters = [{
        'name': 'op',
        'type': 'string',
        'description': 'Operation to perform. One of [init, push, back, peek, parent, get, reset].',
        'required': True
    }, {
        'name': 'url',
        'type': 'string',
        'description': 'Required for push/init. The URL to set or append.',
        'required': False
    }, {
        'name': 'steps',
        'type': 'integer',
        'description': 'For back: the number of levels to go back (default 1).',
        'required': False
    }]

    FILE_PATH = 'nav_chain.json'

    def _load(self):
        try:
            if os.path.exists(self.FILE_PATH):
                with open(self.FILE_PATH, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
        except Exception:
            pass
        return []

    def _save(self, stack):
        try:
            with open(self.FILE_PATH, 'w') as f:
                json.dump(stack, f, ensure_ascii=False)
            return True
        except Exception:
            return False

    def _normalize_url(self, url: str) -> str:
        try:
            return url.strip()
        except Exception:
            return url

    def _push(self, stack, url):
        url = self._normalize_url(url)
        if not url:
            return stack
        # de-duplicate by pruning loop: if exists, cut to that position then re-append only if not top
        idxs = [i for i, item in enumerate(stack) if isinstance(item, dict) and item.get('url') == url]
        if idxs:
            # prune to that index
            new_len = idxs[0] + 1
            stack = stack[:new_len]
            if stack[-1]['url'] != url:
                stack.append({'url': url})
            return stack
        # new url
        stack.append({'url': url})
        return stack

    def call(self, params: str, **kwargs) -> str:
        if not params.strip().endswith("}"):
            if "}" in params.strip():
                params = "{" + get_content_between_a_b("{","}",params) + "}"
            else:
                if not params.strip().endswith("\""):
                    params = params.strip() + "\"}"
                else:
                    params = params.strip() + "}"
        params = "{" + get_content_between_a_b("{","}",params) + "}"

        try:
            data = json5.loads(params)
        except Exception:
            return json.dumps({"ok": False, "error": "invalid params"}, ensure_ascii=False)

        op = str(data.get('op', '')).lower()
        stack = self._load()

        if op == 'reset':
            stack = []
            self._save(stack)
            return json.dumps({"ok": True, "stack": stack}, ensure_ascii=False)

        if op == 'get':
            return json.dumps({"ok": True, "stack": stack}, ensure_ascii=False)

        if op == 'peek':
            top = stack[-1]['url'] if stack else ""
            return json.dumps({"ok": True, "url": top, "stack": stack}, ensure_ascii=False)

        if op == 'parent':
            parent = stack[-2]['url'] if len(stack) >= 2 else ""
            return json.dumps({"ok": True, "url": parent, "stack": stack}, ensure_ascii=False)

        if op == 'init':
            url = self._normalize_url(str(data.get('url', '')))
            if not url:
                return json.dumps({"ok": False, "error": "missing url"}, ensure_ascii=False)
            stack = [{'url': url}]
            print(f"[url_stack] Initialized with root: {url}")
            self._save(stack)
            return json.dumps({"ok": True, "stack": stack}, ensure_ascii=False)

        if op == 'push':
            url = self._normalize_url(str(data.get('url', '')))
            if not url:
                return json.dumps({"ok": False, "error": "missing url"}, ensure_ascii=False)
            old_len = len(stack)
            stack = self._push(stack, url)
            self._save(stack)
            print(f"[url_stack] Pushed {url}, depth: {old_len} -> {len(stack)}")
            return json.dumps({
                "ok": True,
                "message": f"Successfully tracked URL. Current depth: {len(stack)}",
                "current_url": url,
                "stack_depth": len(stack)
            }, ensure_ascii=False)

        if op == 'back':
            steps = data.get('steps', 1)
            try:
                steps = max(1, int(steps))
            except Exception:
                steps = 1
            if len(stack) <= 1:
                return json.dumps({"ok": False, "error": "at root", "message": "Already at root, cannot go back", "stack": stack}, ensure_ascii=False)
            old_len = len(stack)
            new_len = max(1, len(stack) - steps)
            stack = stack[:new_len]
            self._save(stack)
            parent_url = stack[-1]['url']
            print(f"[url_stack] Went back {steps} step(s), depth: {old_len} -> {new_len}, now at: {parent_url}")
            return json.dumps({
                "ok": True,
                "message": f"Went back {steps} level(s). Use visit_url to navigate to this parent URL.",
                "parent_url": parent_url,
                "stack_depth": len(stack)
            }, ensure_ascii=False)

        return json.dumps({"ok": False, "error": "invalid op"}, ensure_ascii=False)

@register_tool('count_usefulness',allow_overwrite=True)
class CountUsefulness(BaseTool):
    """
    description: A tool for counting how many have a usefulness of true
    parameters:
        - name: op
            type: string
            description: Operation to perform. One of [inc, get], when evaluate whether the accumulated useful information is sufficient to answer the current query use get, and when find the observation contains useful information for the query use inc.
            required: true
    """
    description = 'A tool for counting how many have a usefulness of true. When evaluating whether the accumulated useful information is sufficient to answer the current query, this tool is invoked to retrieve the current count. When finding that the observation contains useful information for the query, this tool is invoked to increment the count.'
    parameters = [{
        'name': 'op',
        'type': 'string',
        'description': 'Operation to perform. One of [inc, get], when evaluate whether the accumulated useful information is sufficient to answer the current query use get, and when find the observation contains useful information for the query use inc.',
        'required': True
    }]
    
    def _read_count(self) -> int:
        if not os.path.exists(path):
            with open(path, "w") as f:
                f.write("0")
            return 0
        try:
            with open(path, "r") as f:
                return int(f.read().strip() or 0)
        except Exception:
            return 0

    def _write_count(self, value: int) -> None:
        with open(path, "w") as f:
            f.write(str(max(0, int(value))))
    
    def call(self, params: str, **kwargs) -> str:
        # Normalize to a JSON object string similar to VisitPage parsing tolerance
        if not params.strip().endswith("}"):
            if "}" in params.strip():
                params = "{" + get_content_between_a_b("{","}",params) + "}"
            else:
                if not params.strip().endswith("\""):
                    params = params.strip() + "\"}"
                else:
                    params = params.strip() + "}"
        params = "{" + get_content_between_a_b("{","}",params) + "}"

        try:
            data = json5.loads(params)
        except Exception:
            return "invalid params"

        op = str(data.get('op', '')).lower()
        if op == 'inc':
            current = self._read_count() + 1
            self._write_count(current)
            return str(current)
        elif op == 'get':
            return str(self._read_count())
        else:
            return "invalid op"

@register_tool('query_requirement', allow_overwrite=True)
class QueryRequirement(BaseTool):
    """
    description: A tool to store and retrieve the user's original query for reference.
    parameters:
        - name: op
          type: string
          description: Operation to perform. 'set' to store the query, 'get' to retrieve it.
          required: true
        - name: query
          type: string
          description: The user's query, only required when op is 'set'.
          required: false
    """
    description = 'A tool to store and retrieve the user\'s original query. Use "set" at the beginning to store the query. Use "get" to retrieve it later for reference.'
    parameters = [{
        'name': 'op',
        'type': 'string',
        'description': 'Operation to perform. One of [set, get].',
        'required': True
    }, {
        'name': 'query',
        'type': 'string',
        'description': 'The user query, only required for "set" op.',
        'required': False
    }]

    def _read_query(self) -> str:
        """Read the stored query"""
        path = 'query.txt'
        if not os.path.exists(path):
            return ""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as e:
            print(f"[query_requirement] Error reading query: {e}")
            return ""

    def _write_query(self, query: str) -> None:
        """Write the query to file"""
        path = 'query.txt'
        with open(path, "w", encoding="utf-8") as f:
            f.write(query)

    def call(self, params: str, **kwargs) -> str:
        if not params.strip().endswith("}"):
            if "}" in params.strip():
                params = "{" + get_content_between_a_b("{","}",params) + "}"
            else:
                if not params.strip().endswith("\""):
                    params = params.strip() + "\"}"
                else:
                    params = params.strip() + "}"
        params = "{" + get_content_between_a_b("{","}",params) + "}"

        try:
            data = json5.loads(params)
        except Exception:
            return "invalid params"

        op = str(data.get('op', '')).lower()
        if op == 'set':
            query = data.get('query')
            if not query:
                return "Query is required for 'set' operation."
            self._write_query(query)
            return f"Query stored successfully: {query}"
        elif op == 'get':
            query = self._read_query()
            return f"Original query: {query}" if query else "No query stored yet."
        else:
            return "invalid op"

@register_tool('calculate_understanding_score', allow_overwrite=True)
class CalculateUnderstandingScore(BaseTool):
    """
    description: Calculate the LLM's understanding score (0-100) for the current webpage content to determine if VLM assistance is needed.
    parameters:
        - name: observation
          type: string
          description: The text content of the current page (Markdown format)
          required: true
        - name: query
          type: string
          description: The user's query question
          required: true
        - name: url
          type: string
          description: The current page URL (for special case detection)
          required: false
    """
    description = '''Calculate the LLM's understanding score (0-100) for the current webpage content.
    Score meaning:
    - 80-100: Excellent understanding, text information is clear and complete
    - 60-79: Good understanding, text is basically usable
    - 40-59: Fair understanding, consider using VLM
    - 0-39: Poor understanding, strongly recommend using VLM assistance
    '''

    parameters = [{
        'name': 'observation',
        'type': 'string',
        'description': 'The text content of the current page (Markdown format)',
        'required': True
    }, {
        'name': 'query',
        'type': 'string',
        'description': "The user's query question",
        'required': True
    }, {
        'name': 'url',
        'type': 'string',
        'description': 'The current page URL (for special case detection)',
        'required': False
    }]

    def _evaluate_text_quality(self, observation):
        """Evaluate text content quality (0-25 points)"""
        score = 0
        length = len(observation)

        # 1.1 Length reasonableness (10 points)
        if length < 100:
            score += 0
        elif 100 <= length < 500:
            score += 5
        elif 500 <= length < 5000:
            score += 10
        else:
            score += 8

        # 1.2 Valid character ratio (10 points)
        valid_chars = len(re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9\s.,!?;:，。！？；：]', observation))
        valid_ratio = valid_chars / max(length, 1)
        score += valid_ratio * 10

        # 1.3 Structured elements (5 points)
        has_headers = bool(re.search(r'^#+\s', observation, re.MULTILINE))
        has_lists = bool(re.search(r'^\s*[-*]\s', observation, re.MULTILINE))
        if has_headers:
            score += 2.5
        if has_lists:
            score += 2.5

        return min(score, 25)

    def _evaluate_relevance_with_llm(self, observation, query):
        """Evaluate information relevance using LLM (0-40 points)"""
        prompt = f"""You are an information relevance assessment expert. Please evaluate the relevance between the following webpage content and the user's query.

**User Query**: {query}

**Webpage Content**:
{observation[:2000]}

**Scoring Criteria**:
- 40 points: Highly relevant, contains direct answers or key information
- 30 points: Relevant, contains some useful information
- 20 points: Weakly relevant, may have indirect information
- 10 points: Almost irrelevant
- 0 points: Completely irrelevant

Please return JSON directly:
{{"score": <integer 0-40>, "reason": "<brief reason>"}}
"""

        try:
            client = OpenAI(
                api_key=llm_cfg['api_key'],
                base_url=llm_cfg['model_server'],
            )
            response = client.chat.completions.create(
                model=llm_cfg['model'],
                messages=[{'role': 'user', 'content': prompt}],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            result = json.loads(response.choices[0].message.content)
            return result.get('score', 20), result.get('reason', '')
        except Exception as e:
            print(f"LLM evaluation error: {e}")
            return 20, "LLM evaluation failed, using default score"

    def _evaluate_structure(self, observation):
        """Evaluate page structure clarity (0-20 points)"""
        score = 0

        # 3.1 Paragraph distribution (5 points)
        paragraphs = observation.split('\n\n')
        num_paragraphs = len([p for p in paragraphs if len(p.strip()) > 50])
        if num_paragraphs >= 3:
            score += 5
        elif num_paragraphs >= 1:
            score += 3

        # 3.2 Clickable buttons count (10 points)
        try:
            with open("BUTTON_URL_ADIC.json", "r") as f:
                buttons = json.load(f)
            num_buttons = len(buttons)
            if 5 <= num_buttons <= 30:
                score += 10
            elif 1 <= num_buttons < 5:
                score += 5
            elif num_buttons > 30:
                score += 3
        except Exception:
            score += 5

        # 3.3 Information density (5 points)
        sentences = re.split(r'[。！？.!?]', observation)
        valid_sentences = [s for s in sentences if len(s.strip()) > 20]
        density = len(valid_sentences) / max(len(sentences), 1)
        score += density * 5

        return min(score, 20)

    def _evaluate_special_cases(self, observation, url):
        """Detect special scenarios requiring visual understanding (0-15 points)"""
        score = 15

        url_lower = url.lower() if url else ""
        obs_lower = observation.lower()

        # 4.1 Image gallery or video page
        image_indicators = ['gallery', 'photo', 'image', '图片', '相册']
        video_indicators = ['video', 'play', 'watch', '视频']
        if any(kw in obs_lower or kw in url_lower for kw in image_indicators):
            score -= 10
        if any(kw in obs_lower or kw in url_lower for kw in video_indicators):
            score -= 10

        # 4.2 Interactive content
        interactive_indicators = ['login', 'register', 'captcha', '登录', '注册', '验证码']
        if any(kw in obs_lower for kw in interactive_indicators):
            score -= 5

        # 4.3 Error page
        error_indicators = ['404', 'error', 'not found', '错误', '页面不存在']
        if any(kw in obs_lower for kw in error_indicators):
            score -= 15

        # 4.4 Data visualization page
        viz_indicators = ['chart', 'graph', 'dashboard', '图表', '数据']
        if any(kw in obs_lower for kw in viz_indicators):
            score -= 8

        return max(score, 0)

    def call(self, params: str, **kwargs) -> str:
        # Normalize JSON
        if not params.strip().endswith("}"):
            if "}" in params.strip():
                params = "{" + get_content_between_a_b("{","}",params) + "}"
            else:
                if not params.strip().endswith("\""):
                    params = params.strip() + "\"}"
                else:
                    params = params.strip() + "}"
        params = "{" + get_content_between_a_b("{","}",params) + "}"

        try:
            data = json5.loads(params)
        except Exception:
            return json.dumps({
                "score": 50,
                "recommendation": "fair",
                "error": "invalid params"
            }, ensure_ascii=False)

        observation = data.get('observation', '')
        query = data.get('query', '')
        url = data.get('url', '')

        if not observation or not query:
            return json.dumps({
                "score": 50,
                "recommendation": "fair",
                "error": "missing observation or query"
            }, ensure_ascii=False)

        try:
            # Calculate scores for each dimension
            text_quality = self._evaluate_text_quality(observation)
            relevance, relevance_reason = self._evaluate_relevance_with_llm(observation, query)
            structure = self._evaluate_structure(observation)
            special_cases = self._evaluate_special_cases(observation, url)

            # Final score
            final_score = text_quality + relevance + structure + special_cases
            final_score = max(0, min(100, final_score))

            # Determine recommendation
            if final_score >= 80:
                recommendation = "excellent"
                suggestion = "Text content is highly understandable, continue using LLM analysis."
                should_use_vlm = False
            elif final_score >= 60:
                recommendation = "good"
                suggestion = "Text content is reasonably understandable, LLM should work well."
                should_use_vlm = False
            elif final_score >= 40:
                recommendation = "fair"
                suggestion = "Text content understanding is marginal, consider using VLM for better results."
                should_use_vlm = True
            else:
                recommendation = "poor"
                suggestion = "Text content is difficult to understand, strongly recommend using VLM assistance."
                should_use_vlm = True

            # Display score in UI
            try:
                with st.container():
                    st.markdown(f"**📊 Understanding Score: {int(final_score)}/100** ({recommendation})")
                    with st.expander("View Score Details"):
                        col_a, col_b = st.columns(2)
                        with col_a:
                            st.metric("Text Quality", f"{round(text_quality, 1)}/25")
                            st.metric("Structure", f"{round(structure, 1)}/20")
                        with col_b:
                            st.metric("Relevance", f"{round(relevance, 1)}/40")
                            st.metric("Special Cases", f"{round(special_cases, 1)}/15")
                        st.info(f"💡 {suggestion}")
                        if relevance_reason:
                            st.caption(f"Relevance reason: {relevance_reason}")
            except Exception as e:
                print(f"[WARNING] Failed to display score in UI: {e}")

            return json.dumps({
                "score": int(final_score),
                "recommendation": recommendation,
                "details": {
                    "text_quality": round(text_quality, 2),
                    "relevance": round(relevance, 2),
                    "relevance_reason": relevance_reason,
                    "structure": round(structure, 2),
                    "special_cases": round(special_cases, 2)
                },
                "suggestion": suggestion,
                "should_use_vlm": should_use_vlm
            }, ensure_ascii=False)

        except Exception as e:
            return json.dumps({
                "score": 50,
                "recommendation": "fair",
                "error": str(e),
                "suggestion": "Scoring system error, please judge manually whether to use VLM."
            }, ensure_ascii=False)

@register_tool('use_vlm_analysis', allow_overwrite=True)
class UseVLMAnalysis(BaseTool):
    """
    description: Use Vision Language Model (VLM) to analyze the current page screenshot when text content is difficult to understand.
    parameters:
        - name: query
          type: string
          description: The information to understand/extract from the screenshot
          required: true
        - name: screenshot_path
          type: string
          description: Screenshot file path (optional, uses latest if not provided)
          required: false
        - name: focus_area
          type: string
          description: The area or element to focus on (e.g., "top navigation bar", "main content area")
          required: false
    """
    description = '''Use Vision Language Model (VLM) to analyze the current page screenshot when text content is difficult to understand.
    Applicable scenarios:
    - Understanding score < 40
    - Page contains many images, charts, videos
    - Text extraction failed or incomplete
    '''

    parameters = [{
        'name': 'query',
        'type': 'string',
        'description': 'The information to understand/extract from the screenshot',
        'required': True
    }, {
        'name': 'screenshot_path',
        'type': 'string',
        'description': 'Screenshot file path (optional, uses latest if not provided)',
        'required': False
    }, {
        'name': 'focus_area',
        'type': 'string',
        'description': 'The area or element to focus on (e.g., "top navigation bar", "main content area")',
        'required': False
    }]

    VLM_SYSTEM_PROMPT = """You are a webpage visual analysis expert. The user will provide a webpage screenshot and a query question.

Your tasks:
1. Carefully observe all visual elements in the screenshot (text, images, buttons, layout)
2. Identify information relevant to the query
3. Pay special attention to content that text extraction tools might miss (text in images, chart data, button text)

Output requirements:
- Be concise and direct, answer the query question directly
- If you see relevant articles/links, list the titles and locations
- If there is no relevant information, state it clearly
"""

    vlm_call_count = 0
    MAX_VLM_CALLS_PER_SESSION = 15

    def _load_screenshot(self, screenshot_path=None):
        """Load screenshot as base64"""
        try:
            # If no path provided, use the latest screenshot
            if not screenshot_path:
                if os.path.exists("current_screenshot.json"):
                    with open("current_screenshot.json", "r") as f:
                        info = json.load(f)
                        screenshot_path = info.get("screenshot_path")
                else:
                    # Fallback: use latest image from images folder
                    image_folder = "images/"
                    if os.path.exists(image_folder):
                        image_files = [f for f in os.listdir(image_folder) if f.endswith(('.png', '.jpg', '.jpeg'))]
                        if image_files:
                            # Sort by modification time, get latest
                            image_files_with_time = [(f, os.path.getmtime(os.path.join(image_folder, f))) for f in image_files]
                            latest_file = sorted(image_files_with_time, key=lambda x: x[1], reverse=True)[0][0]
                            screenshot_path = os.path.join(image_folder, latest_file)

            if not screenshot_path or not os.path.exists(screenshot_path):
                return None, "No screenshot available"

            with open(screenshot_path, "rb") as f:
                screenshot_data = f.read()
            screenshot_base64 = base64.b64encode(screenshot_data).decode()
            return screenshot_base64, screenshot_path

        except Exception as e:
            return None, f"Failed to load screenshot: {str(e)}"

    def _call_vlm(self, screenshot_base64, query, focus_area=None):
        """Call VLM to analyze screenshot"""
        try:
            # Check if VLM is configured
            vlm_model = llm_cfg.get('vlm_model', 'qwen3-vl-plus')

            user_content = f"Query: {query}"
            if focus_area:
                user_content += f"\nFocus Area: {focus_area}"
            user_content += "\n\nPlease analyze the webpage screenshot and answer the query."

            messages = [
                {'role': 'system', 'content': self.VLM_SYSTEM_PROMPT},
                {
                    'role': 'user',
                    'content': [
                        {'type': 'text', 'text': user_content},
                        {
                            'type': 'image_url',
                            'image_url': {
                                'url': f"data:image/png;base64,{screenshot_base64}"
                            }
                        }
                    ]
                }
            ]

            client = OpenAI(
                api_key=llm_cfg['api_key'],
                base_url=llm_cfg['model_server'],
            )

            response = client.chat.completions.create(
                model=vlm_model,
                messages=messages,
                max_tokens=500
            )

            return response.choices[0].message.content, "high"

        except Exception as e:
            print(f"VLM call error: {e}")
            return None, str(e)

    def call(self, params: str, **kwargs) -> str:
        # Normalize JSON
        if not params.strip().endswith("}"):
            if "}" in params.strip():
                params = "{" + get_content_between_a_b("{","}",params) + "}"
            else:
                if not params.strip().endswith("\""):
                    params = params.strip() + "\"}"
                else:
                    params = params.strip() + "}"
        params = "{" + get_content_between_a_b("{","}",params) + "}"

        try:
            data = json5.loads(params)
        except Exception:
            return json.dumps({
                "vlm_result": None,
                "status": "failed",
                "error": "invalid params"
            }, ensure_ascii=False)

        query = data.get('query', '')
        screenshot_path = data.get('screenshot_path')
        focus_area = data.get('focus_area')

        if not query:
            return json.dumps({
                "vlm_result": None,
                "status": "failed",
                "error": "missing query"
            }, ensure_ascii=False)

        # Check call limit
        if self.vlm_call_count >= self.MAX_VLM_CALLS_PER_SESSION:
            return json.dumps({
                "vlm_result": None,
                "status": "failed",
                "error": "VLM call limit reached for this session",
                "fallback_suggestion": "Try to continue with text analysis or visit other pages"
            }, ensure_ascii=False)

        # Load screenshot
        screenshot_base64, error_or_path = self._load_screenshot(screenshot_path)
        if screenshot_base64 is None:
            return json.dumps({
                "vlm_result": None,
                "status": "failed",
                "error": error_or_path,
                "fallback_suggestion": "Screenshot not available, continue with text analysis"
            }, ensure_ascii=False)

        # Call VLM
        self.vlm_call_count += 1
        vlm_result, confidence_or_error = self._call_vlm(screenshot_base64, query, focus_area)

        if vlm_result is None:
            return json.dumps({
                "vlm_result": None,
                "status": "failed",
                "error": confidence_or_error,
                "fallback_suggestion": "VLM call failed, continue with text analysis or try other pages"
            }, ensure_ascii=False)

        # Display VLM result in UI
        try:
            with st.container():
                st.markdown(f"**🔍 VLM Analysis #{self.vlm_call_count}**")
                with st.expander("View VLM Result", expanded=True):
                    st.success("VLM analysis completed successfully!")
                    st.write(vlm_result)
                    st.caption(f"Screenshot used: {error_or_path}")
                    st.caption(f"VLM calls used: {self.vlm_call_count}/{self.MAX_VLM_CALLS_PER_SESSION}")
        except Exception as e:
            print(f"[WARNING] Failed to display VLM result in UI: {e}")

        return json.dumps({
            "vlm_result": vlm_result,
            "status": "success",
            "confidence": confidence_or_error,
            "screenshot_used": error_or_path,
            "vlm_calls_used": self.vlm_call_count
        }, ensure_ascii=False)