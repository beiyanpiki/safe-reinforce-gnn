import gymnasium as gym
import numpy as np
import torch
from stable_baselines3 import DQN
from env import example_env, gcn_env_backup, gcn_env
from greatx.training import Trainer
from greatx.nn.models import GCN, SGC
from torch_geometric.datasets import KarateClub
from torch_geometric.transforms import LargestConnectedComponents
from greatx.utils import split_nodes
from greatx.attack.injection import AdvInjection, RandomInjection
from greatx.nn.models import RobustGCN, MedianGCN
from stable_baselines3.common.evaluation import evaluate_policy
from greatx.datasets import GraphDataset

# env = gym.make("CartPole-v1", render_mode="human")
# model = DQN("MlpPolicy", env, verbose=1)
# env = example_env.CustomEnv(size=5)
# model = DQN(
#     policy="MultiInputPolicy",
#     env=env,
#     verbose=1,
#     device="cuda",
# )

# dataset = KarateClub()
dataset = GraphDataset(
    "/home/miku/reinforce-gcn/data", "cora", transform=LargestConnectedComponents()
)
data = dataset[0]
num_features = data.x.size(-1)
num_classes = data.y.max().item() + 1
splits = split_nodes(data.y, random_state=15, train=0.3, test=0.5, val=0.2)


for atk_model_name in ["AdvInjection"]:
    for gnn_model_name in ["SGC"]:
        print(f"{atk_model_name}_{gnn_model_name}\n")
        if atk_model_name == "AdvInjection":
            atk_model = AdvInjection
        elif atk_model_name == "RandomInjection":
            atk_model = RandomInjection

        if gnn_model_name == "GCN":
            gnn_model = GCN
        elif gnn_model_name == "SGC":
            gnn_model = SGC

        # Before
        trainer_before = Trainer(gnn_model(num_features, num_classes), device="cuda")
        trainer_before.fit(data, mask=(splits.train_nodes, splits.val_nodes))
        logs = trainer_before.evaluate(data, splits.test_nodes)
        acc_before = logs["acc"]

        # Attack
        attacker = atk_model(data, device="cuda")
        if atk_model_name == "AdvInjection":
            attacker.setup_surrogate(trainer_before.model)
        attacker.reset()
        if atk_model_name == "AdvInjection":
            attacker.attack(1, feat_budgets=10)
        else:
            attacker.attack(1, feat_limits=(0, 1))
        logs = trainer_before.evaluate(attacker.data(), splits.test_nodes)
        acc_after = logs["acc"]

        # Defense
        env = gcn_env.GcnEnv(
            data=attacker.data(), splits=splits, max_b=20, save_reward=False
        )
        model = DQN(policy="MlpPolicy", env=env, device="cuda", verbose=1, seed=15)

        model.learn(total_timesteps=200000, log_interval=4)
        model.save(f"{gnn_model_name}_{atk_model_name}_karateclub")
        # obs, info = env.reset()
        # print("Reset!")
        # while True:
        #     action, _states = model.predict(obs, deterministic=True)
        #     obs, reward, terminated, truncated, info = env.step(action)
        #     print(obs, reward, info["acc"])
        #     if terminated or truncated:
        #         print(action, _states)
        #         print(info["mask"])
        #         print(attacker.added_nodes())
        #         obs, info = env.reset()
        #         break
