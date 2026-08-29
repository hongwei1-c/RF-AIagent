import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.patches import Circle
from matplotlib.collections import LineCollection
import os

# ================= 参数配置 =================
plt.style.use('dark_background')
fig, ax = plt.subplots(figsize=(8, 8), facecolor='black')
ax.set_facecolor('black')
ax.set_xlim(-1.2, 1.2)
ax.set_ylim(-1.2, 1.2)
ax.set_aspect('equal')
ax.axis('off')

# 配色方案：暗黑科技感 + 射频氛围
colors = ['#ff0033', '#00ffff', '#aa44ff', '#ffaa00', '#33ffcc']

# 粒子数量与运动参数
n_particles = 180
n_layers = 3
particles_per_layer = n_particles // n_layers

# 轨道半径
radii = np.linspace(0.65, 1.05, n_layers)
angular_speeds = [0.85, 1.2, 1.6]
radial_amplitude = 0.08
radial_freq = 2.3

# 拖尾长度
trail_len = 12

# 随机初始角度
angles_init = [np.linspace(0, 2 * np.pi, particles_per_layer, endpoint=False) +
               np.random.uniform(0, 0.2, particles_per_layer) for _ in range(n_layers)]

# 粒子颜色映射
particle_colors = []
for layer in range(n_layers):
    for _ in range(particles_per_layer):
        particle_colors.append(colors[layer % len(colors)])

# 历史轨迹存储
history = [[] for _ in range(n_particles)]
max_history = trail_len

# ================= 创建绘图元素 =================
scat = ax.scatter([], [], s=12, c=[], alpha=0.95, edgecolors='none',
                  linewidth=0, zorder=3, vmin=0, vmax=1)

# 拖尾线段集合
trail_lc = LineCollection([], alpha=0.4, linewidth=1.2,
                          capstyle='round', joinstyle='round', zorder=2)
ax.add_collection(trail_lc)

# 中心光晕
core_glow = Circle((0, 0), 0.12, color='#ff3366', alpha=0.35, zorder=1)
ax.add_patch(core_glow)
inner_glow = Circle((0, 0), 0.22, color='#00aaff', alpha=0.15, zorder=0)
ax.add_patch(inner_glow)

# 装饰性射频波纹
for r in [0.45, 0.8, 1.15]:
    circle = plt.Circle((0, 0), r, fill=False, linestyle='dashed',
                        linewidth=0.8, alpha=0.2, color='cyan')
    ax.add_patch(circle)

# 背景星芒
bg_stars_x = np.random.uniform(-1.1, 1.1, 300)
bg_stars_y = np.random.uniform(-1.1, 1.1, 300)
ax.scatter(bg_stars_x, bg_stars_y, s=0.8, c='white', alpha=0.15, zorder=-1)


# ================= 更新逻辑 =================
def update(frame):
    global history
    t = frame * 0.05

    current_positions = []

    for layer in range(n_layers):
        r_base = radii[layer]
        omega = angular_speeds[layer]
        r_mod = r_base + radial_amplitude * np.sin(radial_freq * t + layer)

        angles_init_layer = angles_init[layer]
        for i, a0 in enumerate(angles_init_layer):
            perturb = 0.12 * np.sin(2.5 * t + i * 0.07)
            angle = a0 + omega * t + perturb

            ellipse_factor_x = 1.0 + 0.05 * np.sin(0.9 * t)
            ellipse_factor_y = 1.0 - 0.03 * np.cos(1.2 * t)
            x = r_mod * np.cos(angle) * ellipse_factor_x
            y = r_mod * np.sin(angle) * ellipse_factor_y

            current_positions.append((x, y))

    pos_arr = np.array(current_positions)
    xs = pos_arr[:, 0]
    ys = pos_arr[:, 1]

    # 更新散点图位置和颜色
    scat.set_offsets(pos_arr)
    if frame == 0:
        scat.set_color(particle_colors)

    # 动态调整粒子大小
    sizes = 8 + 6 * (0.7 + 0.6 * np.sin(5 * t + np.arctan2(ys, xs)))
    scat.set_sizes(sizes)

    # 更新拖尾历史
    for idx, (x, y) in enumerate(zip(xs, ys)):
        history[idx].append((x, y))
        if len(history[idx]) > max_history:
            history[idx].pop(0)

    # 构建线段集合
    all_segments = []
    seg_colors = []
    for idx, hist in enumerate(history):
        if len(hist) >= 2:
            segs = [[hist[k], hist[k + 1]] for k in range(len(hist) - 1)]
            all_segments.extend(segs)
            seg_colors.extend([particle_colors[idx]] * (len(hist) - 1))

    if all_segments:
        trail_lc.set_segments(all_segments)
        trail_lc.set_color(seg_colors)
    else:
        trail_lc.set_segments([])

    # 中心光晕呼吸效果
    alpha_pulse = 0.35 + 0.15 * np.sin(3.5 * t)
    core_glow.set_alpha(alpha_pulse)
    inner_glow.set_alpha(0.12 + 0.08 * np.sin(2.1 * t))

    # 返回更新进度信息
    if frame % 50 == 0 and frame > 0:
        print(f"渲染进度: {frame}/300")

    return scat, trail_lc, core_glow, inner_glow


# ================= 保存到指定路径 =================
# 指定保存路径
output_dir = r"T:\py_prj\AIHFSS\N1\UI"
output_file = os.path.join(output_dir, "rf_particle_animation.gif")

# 确保目录存在
if not os.path.exists(output_dir):
    os.makedirs(output_dir)
    print(f"创建目录: {output_dir}")

print("开始生成动画，请稍候...")
print(f"保存路径: {output_file}")

try:
    # 创建动画
    ani = animation.FuncAnimation(fig, update, frames=300, interval=35, blit=True, repeat=True)

    # 保存为GIF文件
    ani.save(output_file, writer='pillow', fps=30, dpi=120)
    print(f"\n✓ 动画已成功保存到: {output_file}")
    print(f"文件大小约 2-4 MB")
    print(f"你可以直接在文件管理器中打开查看")

except Exception as e:
    print(f"\n保存失败: {e}")
    print("\n可能的原因及解决方法：")
    print("1. 确保目录路径正确且有写入权限")
    print("2. 安装pillow库: pip install pillow")
    print("3. 尝试降低dpi或帧数")

plt.close(fig)
print("\n完成！")