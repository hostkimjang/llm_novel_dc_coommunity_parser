"""Flash Attention ON/OFF 벤치마크"""
from llama_cpp import Llama
import time

model_path = r"C:\Users\kimjang\AppData\Local\llama.cpp\unsloth_GLM-4.7-Flash-GGUF_GLM-4.7-Flash-UD-IQ3_XXS.gguf"
test_prompt = "한국의 수도는"
n_tokens = 100

print("=" * 60)
print("Flash Attention OFF Benchmark")
print("=" * 60)

llm_off = Llama(
    model_path=model_path,
    n_ctx=16384,
    n_gpu_layers=60,
    flash_attn=False,
    verbose=False
)

# Warmup
_ = llm_off(test_prompt, max_tokens=10)

# Benchmark
start = time.perf_counter()
result_off = llm_off(test_prompt, max_tokens=n_tokens)
elapsed_off = time.perf_counter() - start

tokens_off = result_off["usage"]["completion_tokens"]
tps_off = tokens_off / elapsed_off

print(f"Generated: {tokens_off} tokens")
print(f"Time: {elapsed_off:.2f}s")
print(f"Speed: {tps_off:.2f} tokens/sec")
print(f"Output: {result_off['choices'][0]['text'][:100]}...")

del llm_off

print()
print("=" * 60)
print("Flash Attention ON Benchmark")
print("=" * 60)

llm_on = Llama(
    model_path=model_path,
    n_ctx=16384,
    n_gpu_layers=60,
    flash_attn=True,
    verbose=False
)

# Warmup
_ = llm_on(test_prompt, max_tokens=10)

# Benchmark
start = time.perf_counter()
result_on = llm_on(test_prompt, max_tokens=n_tokens)
elapsed_on = time.perf_counter() - start

tokens_on = result_on["usage"]["completion_tokens"]
tps_on = tokens_on / elapsed_on

print(f"Generated: {tokens_on} tokens")
print(f"Time: {elapsed_on:.2f}s")
print(f"Speed: {tps_on:.2f} tokens/sec")
print(f"Output: {result_on['choices'][0]['text'][:100]}...")

del llm_on

print()
print("=" * 60)
print("COMPARISON")
print("=" * 60)
diff = ((tps_on - tps_off) / tps_off) * 100
print(f"Flash OFF: {tps_off:.2f} tok/s")
print(f"Flash ON:  {tps_on:.2f} tok/s")
print(f"Difference: {diff:+.1f}%")
if tps_on > tps_off:
    print(">>> Flash Attention ON is FASTER")
else:
    print(">>> Flash Attention OFF is FASTER")
