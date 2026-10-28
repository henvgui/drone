# ESC V1.0 引脚分配表 A

日期：2026-10-27。器件：**STM32G071CBT6，LQFP48，128KB Flash**；**DRV8323SRTAR，RTA 40脚 WQFN**。

本表作为第一版原理图的引脚分配基线。依据 AM32 v2.21 的 `GEN_128K_G071 / HARDWARE_GROUP_G0_A`，提交 `6b3ef3d15228e8d70244bd6e3bd87c7eac939d6f`。已核对封装脚号、复用功能、参考固件定义及资源冲突；尚未做板级验证。DRV 的 SPI 初始化、故障处理、外围电路和采样参数仍需后续实现，通用目标不能直接作为本板可用固件。

表中的 GPIO 是程序使用的名字；“MCU脚号”是原理图符号和实物封装的脚号，两者必须同时匹配。统一约定 **AM32 A相 = U相，B相 = V相，C相 = W相**。DRV 的 A/B/C 相也按此对应。

## 1. 六路桥臂控制

DRV 采用 **6x PWM 模式**。每相分别接一条上管控制线、一条下管控制线。MCU 接的是驱动器的 INH/INL 输入，MOSFET 栅极另接驱动器 GH/GL 输出。

| 网络名 | 用途 | MCU GPIO | MCU脚号 | 外设功能 | AF | 接 DRV8323S | DRV脚号 |
| --- | --- | --- | ---: | --- | ---: | --- | ---: |
| U_H | U相上管控制 | PA10 | 32 | TIM1_CH3 | 2 | INHA | 34 |
| U_L | U相下管控制 | PB1 | 20 | TIM1_CH3N | 2 | INLA | 35 |
| V_H | V相上管控制 | PA9 | 29 | TIM1_CH2 | 2 | INHB | 36 |
| V_L | V相下管控制 | PB0 | 19 | TIM1_CH2N | 2 | INLB | 37 |
| W_H | W相上管控制 | PA8 | 28 | TIM1_CH1 | 2 | INHC | 38 |
| W_L | W相下管控制 | PA7 | 18 | TIM1_CH1N | 2 | INLC | 39 |

选择理由：保留 G0_A 的整组映射，可以继续使用现有换相函数。U相使用CH3属于该参考布局的正常映射，不要求U/V/W依次使用CH1/CH2/CH3。

这些引脚会在定时器复用输出与普通 GPIO 输出之间切换，分别实现 PWM、低侧导通和悬空。不能把六条线全部改成始终运行的普通互补 PWM。默认使用高电平有效控制；DRV 6x 模式的输入 `INH/INL=00` 对应上下管关断，`10` 为上管导通，`01` 为下管导通。

**PA9/PA10重映射是必须处理的适配项。** 上游 `Mcu/g071/Src/peripherals.c` 默认设置 `PA11_RMP`、`PA12_RMP`，让PA11/PA12焊盘承载PA9/PA10功能。本表采用原生PA9脚29、PA10脚32，因此本板构建必须定义 `NO_PA11_PA12_REMAP`，跳过上游的重映射设置；板级初始化还应显式清除这两个重映射位，消除前级程序可能留下的状态。PA11脚33、PA12脚34暂不分配功能。

## 2. DShot、SPI与驱动器管理

下表“方向”以MCU为参照。SPI2先采用轮询收发，不占用DMA。

| 网络名 | 用途 | MCU GPIO | MCU脚号 | 外设/配置 | 方向 | 接 DRV8323S | DRV脚号 |
| --- | --- | --- | ---: | --- | --- | --- | ---: |
| DSHOT | 油门输入；可复用维护通信 | PB4 | 43 | TIM3_CH1，AF1；DMA1_CH1 | 输入/按协议切换 | 外部信号焊盘 | — |
| DRV_SCK | SPI时钟 | PB13 | 25 | SPI2_SCK，AF0 | 输出 | SCLK | 28 |
| DRV_MISO | 读取驱动器状态 | PB14 | 26 | SPI2_MISO，AF0 | 输入 | SDO | 26 |
| DRV_MOSI | 发送驱动器配置 | PB15 | 27 | SPI2_MOSI，AF0 | 输出 | SDI | 27 |
| DRV_nCS | SPI片选，低有效 | PB9 | 48 | 普通GPIO，软件片选 | 输出 | nSCS | 29 |
| DRV_EN | 驱动器使能/休眠控制 | PB8 | 47 | 普通GPIO | 输出 | ENABLE | 30 |
| DRV_nFAULT | 故障通知，低有效 | PB12 | 24 | GPIO输入/EXTI12；可进一步用TIM1_BKIN AF2 | 输入 | nFAULT | 25 |
| DRV_CAL | 电流放大器校准控制预留 | PB2 | 21 | 普通GPIO；正常运行保持低 | 输出 | CAL | 31 |

选择理由：

- PB4沿用主参考和已找到的 `AM32_G071_BOOTLOADER_PB4_V19.hex`，应用与Bootloader使用同一信号焊盘。
- SPI2的PB13/PB14/PB15避开PA7桥臂、PB4输入、PB3/PB7比较器和PA5/PA6采样，也保留PB6串口遥测。不能照搬SPI1的PA5/PA6/PA7接法。
- PB9作为普通GPIO控制片选，不需要选择它的SPI2_NSS复用。
- PB12既能读取故障，也保留TIM1紧急关断输入的条件。**上游默认关闭TIM1 Break；接上此线不会自动实现紧急关断。** 后续必须增加配置和故障处理，并处理当前换相期间GPIO直驱状态下的关断。DRV内部保护与MCU关断流程都需验证。
- CAL保留为可控引脚，后续确定采样方案时再落实校准方法。

## 3. 下载、遥测和状态指示

| 网络名 | MCU GPIO/端口 | MCU脚号 | 分配 | 说明 |
| --- | --- | ---: | --- | --- |
| SWDIO | PA13 | 35 | SWD，保留默认AF0 | 接ST-LINK |
| SWCLK | PA14 | 36 | SWD，保留默认AF0 | PA14兼有BOOT0功能，开发阶段保持调试用途 |
| NRST | PF2-NRST | 10 | 复位功能 | 引出至SWD接口；不改为普通GPIO |
| SWD_VREF | 板上3V3网络 | — | 调试器目标电压参考 | 接口提供3V3参考、GND；调试器是否给板供电需按实物确定 |
| TLM_TX | PB6 | 45 | USART1_TX，AF0 | 预留遥测焊盘；上游使用单线半双工、开漏、115200波特率 |
| STATUS_LED | PC6 | 30 | 普通GPIO输出 | 预留状态LED；接法和限流电阻后续确定 |

PB6预留并不意味着现有固件具备任意文本调试串口；打印日志需另加代码。PB7已用于反电动势检测，不能再按USART1_RX接成一组普通双线串口。PC6需要在本板代码中额外开启GPIOC时钟并初始化，现有G071通用GPIO初始化只开启GPIOA/B。

## 4. 暂缓电路的引脚预留

本节只固定资源，不确定分压、滤波、电流拓扑或器件参数。表中的检测信号必须经过后续设计的调理电路，不能直接接电池电压或电机相线。

| 预留网络 | MCU GPIO | MCU脚号 | 资源 | 当前状态 |
| --- | --- | ---: | --- | --- |
| BEMF_U | PB7 | 46 | COMP2_INM，IO2 | 与G0_A的A相反馈对应 |
| BEMF_V | PB3 | 42 | COMP2_INM，IO1 | 与G0_A的B相反馈对应 |
| BEMF_W | PA2 | 13 | COMP2_INM，IO3 | 与G0_A的C相反馈对应 |
| BEMF_REF | PA3 | 14 | COMP2_INP，IO3 | 参考电路暂缓 |
| CURRENT_SENSE | PA5 | 16 | ADC_IN5 | 保留上游默认电流通道；DRV的SOA/SOB/SOC尚未选定 |
| VBAT_SENSE | PA6 | 17 | ADC_IN6 | 保留上游默认电压通道 |
| TEMP_SENSE | PA0 | 11 | ADC_IN0 | 可选外部NTC；启用需修改ADC序列及换算 |

比较器模拟输入不使用AF编号；固件通过COMP输入选择器切换三相。BEMF_REF、MCU的VREF+和DRV的VREF是不同用途的信号，不能因为都有“参考”二字就连在一起。

## 5. 电源脚与未分配引脚

| MCU脚号 | 名称 | 原理图要求 |
| ---: | --- | --- |
| 4 | VBAT | MCU备份域供电，本板接3.3V；不是动力电池输入 |
| 5 | VREF+ | ADC等的模拟电压参考，本版按3.3V参考设计并去耦 |
| 6 | VDD/VDDA | 3.3V数字/模拟供电并去耦 |
| 7 | VSS/VSSA | 接控制地 |

未分配：PC13(1)、PC14(2)、PC15(3)、PF0(8)、PF1(9)、PA1(12)、PA4(15)、PB10(22)、PB11(23)、PC7(31)、PA11(33)、PA12(34)、PA15(37)、PD0(38)、PD1(39)、PD2(40)、PD3(41)、PB5(44)。括号内为LQFP48脚号。当前参考使用内部HSI/PLL，PF0/PF1可保留为后续外部晶振位置；不据此新增本版晶振要求。

DRV的供电、电荷泵、六路栅极输出、放大器输入输出及散热焊盘，留待其外围原理图阶段设计。本表没有给出一份可独立制造的完整接线图。

## 6. 上电约束与固件适配清单

| 信号 | 从上电到允许电机运行之前的要求 |
| --- | --- |
| DRV_EN | 外部下拉保证MCU复位和Bootloader期间保持低；软件初始化先写低，再设为输出 |
| 六路INH/INL | 外围保证未受控时为低；使能驱动器前，六路均处于低电平；具体下拉参数后续确定 |
| DRV_nCS | 外部上拉至3.3V，未通信时保持高 |
| DRV_MISO、DRV_nFAULT | DRV的SDO和nFAULT均为开漏输出，分别需要外部上拉至3.3V |
| DRV_CAL | 外部保证默认为低，校准时才主动拉高 |
| DRV_SCK | SPI空闲电平按DRV时序配置；DRV在下降沿采入SDI，初始采用SPI Mode 1并按官方时序读回验证 |

不要把“MCU程序刚开始写低”当成复位期间已经写低。Bootloader阶段应用尚未运行，关闭功率桥依赖上述硬件默认状态。使能后进行SPI配置时也必须保持六路输入全低，不能假设ENABLE低时SPI仍可正常通信。

板级代码尚待完成的具体项：

1. 使用本表原生PA9/PA10布局：定义 `NO_PA11_PA12_REMAP`，并在TIM1/GPIO输出初始化前显式关闭两个重映射位。
2. 初始化时关闭UCPD的dead-battery下拉功能。ST手册脚注特别涉及PA8、PB15等引脚，分别被本板用于PWM和SPI；对应LL接口为 `LL_SYSCFG_DisableDBATT(LL_SYSCFG_UCPD1_STROBE | LL_SYSCFG_UCPD2_STROBE)`。
3. 添加SPI2、PB9片选、PB8使能、PB2校准、PB12故障和PC6状态灯初始化；SPI先用轮询。
4. 接入DRV唤醒、6x PWM配置、配置读回与故障处理；死区、驱动强度和保护阈值后续计算，不直接继承参考目标数值作为合格参数。
5. PB12如采用EXTI12，与现有DShot处理共用 `EXTI4_15_IRQHandler`。现有处理函数直接清EXTI15并调用 `processDshot()`，必须改为按挂起标志分别分发，不能覆盖为另一个独立中断函数。
6. 若启用TIM1_BKIN，另行配置AF2、低电平故障极性、关断和恢复流程；仅写本表不会启用此功能。
7. 反馈及采样电路确定后，再校核比例、量程、极性、ADC序列和默认参数。外部NTC需要软件支持，预留脚不能视为已经实现温度保护。

资源检查：PWM使用TIM1 CH1/1N、CH2/2N、CH3/3N；DShot使用TIM3_CH1和DMA1_CH1；ADC沿用DMA1_CH2；USART1遥测沿用DMA1_CH3；SPI2轮询不增加DMA占用。TIM1 CH4/CH5在上游有ADC触发/比较器消隐用途，不拿来另接外设。26个已分配/预留信号占用不同GPIO和不同物理焊盘，13个DRV控制/通信信号也未复用焊盘，SWD保留。

已实际运行GNU Arm预处理器，检查GEN_128K_G071展开后的六路桥臂、PB4输入、ADC默认通道及比较器选择与本表一致，未启用64KB定义或高低侧反相定义；加入 `NO_PA11_PA12_REMAP` 后，初始化函数中的默认重映射调用被移除。机器可读分配与核对结果保存在 `calculations/esc_v1_pinmap.json`，预处理输出在 `build/pin-audit/`。这是资源和预处理检查，没有完成新的板级固件构建或硬件测试。

## 7. 核对依据与交付范围

- [ST官方数据手册 DS12232 Rev5](https://www.st.com/resource/en/datasheet/stm32g071cb.pdf)：第40页图7，LQFP48脚号；第43至48页表12，模拟功能与重映射/UCPD脚注；第49至50页表13/14，PA/PB复用。
- [TI官方DRV832x数据手册 SLVSDJ3D](https://www.ti.com/lit/ds/symlink/drv8323.pdf)：第8页图6-6，DRV8323S RTA40；第8至9页表6-3，输入、SPI、开漏和CAL定义；第32页表8-2，6x PWM真值表；第53页，SPI时序约束。
- [AM32固定提交的targets.h](https://github.com/am32-firmware/AM32/blob/6b3ef3d15228e8d70244bd6e3bd87c7eac939d6f/Inc/targets.h)：GEN_128K_G071和G0_A定义。
- 同提交 `Mcu/g071/Src/peripherals.c`、`phaseouts.c`、`comparator.c`、`serial_telemetry.c`、`ADC.c`和`stm32g0xx_it.c`：实际初始化、换相、遥测、DMA和中断路径。检查记录见 `build/pin-audit`。

本次完成的是**引脚与资源选择**。接下来可以据此建立MCU最小系统与控制接口原理图，再按用户节奏恢复暂缓的外围电路设计。原理图审查、完整本板固件、上电波形和电机测试完成后，才能确认整板可用。
