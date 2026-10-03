"""Golden test cases (spec section 11.6): what the direct script runs, and the matching harness run.

Placeholders: {gen} {ref} {prompts_jsonl} {prompts_csv} {work} are filled with fixture paths.
"random_scores" lists scores that come from randomness the harness cannot seed
(UNSEEDED_RANDOMNESS). The golden test checks only that they are present and finite
(amendment A10); every other score gets the section 11.6 tolerance.
"""

CASES = {
    "aesthetics_audiobox": [
        {
            "case": "gen_small",
            "metric_id": "aesthetics.audiobox@1",
            "direct": ["aesthetics_direct.py", "--gen", "{gen}", "--batch-size", "8"],
            "harness": ["--metrics", "aesthetics.audiobox@1", "--batch-size", "8"],
        },
    ],
    "clapscore_laion": [
        {
            "case": "gen_small",
            "metric_id": "clapscore.laion-music@1",
            "direct": ["clap_direct.py", "--gen", "{gen}", "--prompts", "{prompts_jsonl}"],
            "harness": ["--prompts", "{prompts_csv}", "--metrics", "clapscore.laion-music@1"],
        },
    ],
    "fad_fadtk": [
        {
            "case": "vggish-dir",
            "metric_id": "fad.vggish@1",
            "direct": ["fad_direct.py", "--model", "vggish", "--ref", "{ref}", "--gen", "{gen}", "--workers", "8"],
            "harness": ["--reference", "{ref}", "--metrics", "fad.vggish@1", "--workers", "8"],
            "random_scores": ["fad_inf", "fad_inf_r2"],
        },
        {
            "case": "vggish-fma_pop",
            "metric_id": "fad.vggish@1",
            "direct": ["fad_direct.py", "--model", "vggish", "--ref", "fma_pop", "--gen", "{gen}", "--workers", "8"],
            "harness": ["--reference", "bundled:fma_pop", "--metrics", "fad.vggish@1", "--workers", "8"],
            "random_scores": ["fad_inf", "fad_inf_r2"],
        },
        {
            "case": "clap-laion-music-dir",
            "metric_id": "fad.clap-laion-music@1",
            "direct": ["fad_direct.py", "--model", "clap-laion-music", "--ref", "{ref}", "--gen", "{gen}", "--workers", "8"],
            "harness": ["--reference", "{ref}", "--metrics", "fad.clap-laion-music@1", "--workers", "8"],
            "random_scores": ["fad_inf", "fad_inf_r2"],
        },
        {
            "case": "encodec-emb-dir",
            "metric_id": "fad.encodec-emb@1",
            "direct": ["fad_direct.py", "--model", "encodec-emb", "--ref", "{ref}", "--gen", "{gen}", "--workers", "8"],
            "harness": ["--reference", "{ref}", "--metrics", "fad.encodec-emb@1", "--workers", "8"],
            "random_scores": ["fad_inf", "fad_inf_r2"],
        },
    ],
    "kad_kadtk": [
        {
            "case": "vggish-dir",
            "metric_id": "kad.vggish@1",
            "direct": ["kad_direct.py", "--model", "vggish", "--ref", "{ref}", "--gen", "{gen}", "--workers", "8"],
            "harness": ["--reference", "{ref}", "--metrics", "kad.vggish@1", "--workers", "8"],
            "random_scores": [],
        },
        {
            "case": "clap-laion-music-dir",
            "metric_id": "kad.clap-laion-music@1",
            "direct": ["kad_direct.py", "--model", "clap-laion-music", "--ref", "{ref}", "--gen", "{gen}", "--workers", "8"],
            "harness": ["--reference", "{ref}", "--metrics", "kad.clap-laion-music@1", "--workers", "8"],
            "random_scores": [],
        },
    ],
}
