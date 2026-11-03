python3 -m embodiment.rental doctor --prefix /workspace/viper --root /workspace/runs/viper


python3 -m embodiment.rental setup --prefix /workspace/viper --root /workspace/runs/viper
python3 -m embodiment.rental setup --prefix /workspace/viper --root /workspace/runs/viper --execute --accept-isaac-license
python3 -m embodiment.rental qualify --prefix /workspace/viper --root /workspace/runs/viper --execute --allow-gpu --accept-isaac-license
python3 -m embodiment.rental collect --prefix /workspace/viper --root /workspace/runs/viper --execute --allow-gpu --accept-isaac-license
python3 -m embodiment.rental report --prefix /workspace/viper --root /workspace/runs/viper


python3 -m embodiment.rental setup --prefix /workspace/viper --root /workspace/runs/viper --training-runtime --execute --accept-isaac-license


python3 -m embodiment.rental g3 --prefix /workspace/viper --root /workspace/runs/viper --execute --allow-gpu --allow-training --accept-isaac-license
python3 -m embodiment.rental m0 --prefix /workspace/viper --root /workspace/runs/viper --steps 2000 --save-steps 500 --execute --allow-gpu --allow-training --accept-isaac-license
python3 -m embodiment.rental report --prefix /workspace/viper --root /workspace/runs/viper


export PREFIX=/workspace/viper
export RUN=/workspace/runs/viper
export TRAIN_PY="$PREFIX/sources/GR00T/.venv/bin/python"
export SIM_PY="$PREFIX/simulation/bin/python"
export DATASET_A="$RUN/session/pilot/exports/openmanipulator_x/train"
export DATASET_B="$RUN/session/pilot/exports/franka_panda/train"
export CAMPAIGN="$RUN/campaign"
export G3="$RUN/g3"
export HF_HOME="$PREFIX/cache/huggingface"
export HF_HUB_CACHE="$HF_HOME/hub"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 WANDB_MODE=disabled
export VIPER_ACTION_CONTRACT_LIBRARY="$PREFIX/native/libviper_action_contract.so"
export VIPER_ASSET_CACHE="$PREFIX/robot_cache"
export VIPER_PANDA_USD="$PREFIX/assets/Isaac/IsaacLab/Robots/FrankaEmika/panda_instanceable.usd"
export LD_LIBRARY_PATH="$PREFIX/codec${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export OMNI_KIT_ACCEPT_EULA=YES


"$TRAIN_PY" -c 'import sys; from pathlib import Path; from embodiment.m0 import verify; result=verify(Path(sys.argv[1])); print(result); assert result["status"] == "PASS", "M0 failed; preserve results and stop"' \
  "$CAMPAIGN/m0_evaluate_a/attempt-0000/evaluation"


for STAGE in train_b_only train_a_to_b evaluate_b_only evaluate_a_to_b; do
  "$TRAIN_PY" -m embodiment.training_campaign \
    --source "$PREFIX/sources/GR00T" --dataset-a "$DATASET_A" --dataset-b "$DATASET_B" \
    --pretrained "$PREFIX/models/groot" --root "$CAMPAIGN" --smoke-root "$G3" \
    --simulation-python "$SIM_PY" --steps 2000 --save-steps 500 \
    --batch-size 1 --gradient-accumulation 12 --stage "$STAGE" --execute || break
done


"$TRAIN_PY" -m embodiment.paired \
  --baseline "$CAMPAIGN/evaluate_b_only/attempt-0000/evaluation/report.json" \
  --transfer "$CAMPAIGN/evaluate_a_to_b/attempt-0000/evaluation/report.json" \
  --output "$CAMPAIGN/paired.json"
