--[[
	DinoAnimator (Script, RunContext = Client) — gerado pelo dinomaker.

	Toca as animações embutidas na pasta "Animations" (KeyframeSequence)
	escrevendo direto em Motor6D.Transform. Não precisa publicar nada.

	Estado automático:
	  Death  -> Humanoid morreu (Health <= 0)
	  Fly    -> atributo Flying = true (só dinos com asas)
	  Run    -> velocidade > meio caminho entre WalkSpeed e RunSpeed
	  Walk   -> velocidade > 0.5
	  Idle   -> parado
	Ações (uma vez): servidor faz model:SetAttribute("Action", "Attack"|"Roar"|"Hit"|"Eat")
	e incrementa "ActionNonce" (use o ModuleScript DinoAPI).
]]

local RunService = game:GetService("RunService")

-- Versão A: script dentro do Model. Versão B: dentro da pasta DinoKit do modelo importado.
local container = script.Parent
local isKit = not container:IsA("Model")
local model = isKit and container.Parent or container
if isKit then
	local t0 = os.clock()
	while not model:GetAttribute("DinoReady") and os.clock() - t0 < 30 do
		task.wait(0.1)
	end
end
local hum = model:WaitForChild("Humanoid", 15)
local root = model:WaitForChild("HumanoidRootPart", 15)
local folder = container:WaitForChild("Animations", 15)
if not (hum and root and folder) then
	return
end

local FADE = 0.18

-- driver: aplica a pose (nome -> CFrame) no rig
local driver
if isKit then
	local Rig = require(container:WaitForChild("DinoRig"))
	driver = Rig.newDriver(model, root, container)
else
	local motors = {}
	for _, d in ipairs(model:GetDescendants()) do
		if d:IsA("Motor6D") and d.Part1 then
			motors[d.Part1.Name] = d
		end
	end
	driver = {
		has = function(name)
			return motors[name] ~= nil
		end,
		apply = function(pose)
			for name, cf in pairs(pose) do
				local m = motors[name]
				if m then
					m.Transform = cf
				end
			end
		end,
	}
end

-- KeyframeSequence -> lista ordenada de {t, poses}
local clips = {}
local function loadClip(kfs)
	local keys = {}
	for _, kf in ipairs(kfs:GetChildren()) do
		if kf:IsA("Keyframe") then
			local poses = {}
			for _, p in ipairs(kf:GetDescendants()) do
				if p:IsA("Pose") and p.Weight > 0 and driver.has(p.Name) then
					poses[p.Name] = p.CFrame
				end
			end
			table.insert(keys, { t = kf.Time, poses = poses })
		end
	end
	table.sort(keys, function(a, b)
		return a.t < b.t
	end)
	if #keys == 0 then
		return nil
	end
	return { keys = keys, length = keys[#keys].t, loop = kfs.Loop, name = kfs.Name }
end
for _, kfs in ipairs(folder:GetChildren()) do
	if kfs:IsA("KeyframeSequence") then
		clips[kfs.Name] = loadClip(kfs)
	end
end

-- VFX (atributo VFX liga/desliga; tema em VFXTheme)
local fx = { aura = {}, breath = {}, dust = {}, burst = {}, glow = {} }
for _, d in ipairs(model:GetDescendants()) do
	if d:IsA("ParticleEmitter") then
		local list = fx[string.lower(d.Name)]
		if list then
			table.insert(list, d)
		end
	elseif d:IsA("PointLight") and d.Name == "Glow" then
		table.insert(fx.glow, d)
	end
end
local function fxOn()
	return model:GetAttribute("VFX") ~= false
end
local deadFx = false
local function applyAura()
	local on = fxOn() and not deadFx
	for _, e in ipairs(fx.aura) do
		e.Enabled = on
	end
	for _, l in ipairs(fx.glow) do
		l.Enabled = on
	end
	if not on then
		for _, e in ipairs(fx.dust) do
			e.Rate = 0
		end
	end
end
local function burst(list, n, delay)
	if not fxOn() then
		return
	end
	task.delay(delay or 0, function()
		for _, e in ipairs(list) do
			e:Emit(n)
		end
	end)
end
model:GetAttributeChangedSignal("VFX"):Connect(applyAura)
applyAura()
local FX_ON_ACTION = {
	Roar = function() burst(fx.breath, 45, 0.45) end,
	Attack = function() burst(fx.breath, 18, 0.4) end,
	Hit = function() burst(fx.burst, 14, 0) end,
}

local function sample(clip, t, out)
	local keys = clip.keys
	local n = #keys
	if clip.loop and clip.length > 0 then
		t = t % clip.length
	elseif t >= clip.length then
		t = clip.length
	end
	local lo, hi = 1, n
	while hi - lo > 1 do
		local mid = math.floor((lo + hi) / 2)
		if keys[mid].t <= t then
			lo = mid
		else
			hi = mid
		end
	end
	local a, b = keys[lo], keys[hi]
	local span = b.t - a.t
	local alpha = 0
	if span > 0 then
		alpha = math.clamp((t - a.t) / span, 0, 1)
	end
	for name, cfa in pairs(a.poses) do
		local cfb = b.poses[name] or cfa
		out[name] = cfa:Lerp(cfb, alpha)
	end
	return out
end

-- estado
local current, currentT, speedScale = nil, 0, 1
local prevPose, fadeT = nil, 0
local action, actionT, actionPlays = nil, 0, 0
local dead = false
local lastPose = {}

local function play(name)
	if current == name then
		return
	end
	if not clips[name] then
		return
	end
	prevPose = {}
	for k, v in pairs(lastPose) do
		prevPose[k] = v
	end
	fadeT = 0
	current = name
	currentT = 0
end

local function startAction(name)
	if not clips[name] or dead then
		return
	end
	prevPose = {}
	for k, v in pairs(lastPose) do
		prevPose[k] = v
	end
	fadeT = 0
	action = name
	actionT = 0
	actionPlays = (name == "Eat") and 2 or 1
	if FX_ON_ACTION[name] then
		FX_ON_ACTION[name]()
	end
end

model:GetAttributeChangedSignal("ActionNonce"):Connect(function()
	local a = model:GetAttribute("Action")
	if type(a) == "string" and a ~= "" then
		startAction(a)
	end
end)

hum.Died:Connect(function()
	dead = true
	action = nil
	play("Death")
	burst(fx.burst, 30, 0.6)
	deadFx = true
	applyAura()
end)

local function chooseBase()
	if dead or hum.Health <= 0 then
		dead = true
		return "Death", 1
	end
	if model:GetAttribute("Flying") and clips.Fly then
		return "Fly", 1
	end
	local v = root.AssemblyLinearVelocity
	local speed = Vector3.new(v.X, 0, v.Z).Magnitude
	local ws = model:GetAttribute("WalkSpeed") or 8
	local rs = model:GetAttribute("RunSpeed") or ws * 2
	if speed > (ws + rs) * 0.5 and clips.Run then
		return "Run", math.clamp(speed / rs, 0.5, 2)
	elseif speed > 0.5 and clips.Walk then
		return "Walk", math.clamp(speed / ws, 0.5, 2)
	end
	return "Idle", 1
end

local camera = workspace.CurrentCamera
local accum = 0

RunService.PreSimulation:Connect(function(dt)
	if not model.Parent then
		return
	end
	-- LOD: longe da câmera atualiza menos
	accum = accum + dt
	local cam = workspace.CurrentCamera or camera
	if cam then
		local dist = (cam.CFrame.Position - root.Position).Magnitude
		local interval = dist > 300 and 0.2 or (dist > 150 and 0.066 or 0)
		if accum < interval then
			return
		end
	end
	local step = accum
	accum = 0

	local base, rate = chooseBase()
	if base ~= current and not (current == "Death" and dead) then
		play(base)
	end
	speedScale = rate
	local dustRate = 0
	if fxOn() and not dead then
		if base == "Run" then
			dustRate = 18
		elseif base == "Walk" then
			dustRate = 4
		end
	end
	for _, e in ipairs(fx.dust) do
		if e.Rate ~= dustRate then
			e.Rate = dustRate
		end
	end
	currentT = currentT + step * speedScale
	fadeT = fadeT + step

	local pose = {}
	if action and not dead then
		actionT = actionT + step
		local clip = clips[action]
		if actionT >= clip.length then
			actionPlays = actionPlays - 1
			if actionPlays <= 0 then
				action = nil
				prevPose = {}
				for k, v in pairs(lastPose) do
					prevPose[k] = v
				end
				fadeT = 0
			else
				actionT = 0
			end
		end
		if action then
			sample(clips[action], actionT, pose)
		end
	end
	if not action then
		sample(clips[current], currentT, pose)
	end

	local w = math.clamp(fadeT / FADE, 0, 1)
	local out = {}
	for name, cf in pairs(pose) do
		local final = cf
		if prevPose and w < 1 and prevPose[name] then
			final = prevPose[name]:Lerp(cf, w)
		end
		out[name] = final
		lastPose[name] = final
	end
	driver.apply(out)
end)
