#!/usr/bin/env python3
"""GLM chat_template 수정 테스트"""

from gguf import GGUFReader

model_path = r"C:\Users\kimjang\AppData\Local\llama.cpp\unsloth_GLM-4.7-Flash-GGUF_GLM-4.7-Flash-UD-IQ3_XXS.gguf"
reader = GGUFReader(model_path, 'r')
val = reader.fields['tokenizer.chat_template']
template = bytes(val.parts[val.data[0]]).decode('utf-8')

print("=== ORIGINAL TEMPLATE (last 500 chars) ===")
print(template[-500:])
print()

# enable_thinking=False로 강제 설정
# 마지막 줄에서 '<think>'를 '</think>'로 변경
old_line = "{{- '</think>' if (enable_thinking is defined and not enable_thinking) else '<think>' -}}"
new_line = "{{- '</think>' -}}"

fixed = template.replace(old_line, new_line)

print("=== MODIFIED TEMPLATE (last 500 chars) ===")
print(fixed[-500:])
print()

# 테스트
from llama_cpp import Llama
from llama_cpp import llama_chat_format as lcf

print("=== Testing with modified template (enable_thinking=False) ===")
llm = Llama(model_path=model_path, n_ctx=2048, n_gpu_layers=60, verbose=False)

# 수정된 템플릿으로 formatter 생성
formatter = lcf.Jinja2ChatFormatter(
    template=fixed,
    eos_token="</s>",
    bos_token="<s>",
    add_generation_prompt=True,
)
chat_handler = lcf.chat_formatter_to_chat_completion_handler(formatter)

# chat_handler로 llm 업데이트
llm.chat_handler = chat_handler

messages = [{"role": "user", "content": "Hi, just say hello in one word"}]
response = llm.create_chat_completion(messages=messages, max_tokens=50, stream=False)

print("Response:")
print(response['choices'][0]['message']['content'])
