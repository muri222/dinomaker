--[[
	DinoBrain (Script, RunContext = Server) — gerado pelo dinomaker.

	Atributos do Model (editáveis no Studio):
	  WalkSpeed / RunSpeed  velocidades que batem com a passada da animação
	  Wander (bool)         passeia sozinho perto do ponto inicial (teste rápido)
	  WanderRadius          raio do passeio
	  Action / ActionNonce  dispara ações (use DinoAPI.Play)
	  Flying (bool)         toca a animação Fly (dinos com asas)
]]

-- Versão A: dentro do Model. Versão B: dentro da pasta DinoKit (monta o rig no Play).
local container = script.Parent
local model = container:IsA("Model") and container or nil
if not model then
	local Rig = require(container:WaitForChild("DinoRig"))
	model = Rig.findTarget(container)
	if not model then
		warn("[DinoKit] Não achei o modelo do dino. Arraste a pasta DinoKit para dentro do modelo importado pelo Importar 3D.")
		return
	end
	if not Rig.setup(model, container) then
		return
	end
end
local hum = model:WaitForChild("Humanoid")
local root = model:WaitForChild("HumanoidRootPart")
local API = require(container:WaitForChild("DinoAPI"))

hum.WalkSpeed = model:GetAttribute("WalkSpeed") or hum.WalkSpeed

-- voo (dinos com asas): sobe o HipHeight enquanto Flying = true
local anims = container:FindFirstChild("Animations")
local canFly = anims and anims:FindFirstChild("Fly") ~= nil
local baseHip = hum.HipHeight
if model:GetAttribute("FlyHeight") == nil then
	model:SetAttribute("FlyHeight", math.max(6, baseHip * 4))
end
local function applyFlying()
	if canFly and model:GetAttribute("Flying") then
		hum.HipHeight = baseHip + (model:GetAttribute("FlyHeight") or 8)
		hum.WalkSpeed = model:GetAttribute("RunSpeed") or hum.WalkSpeed
	else
		hum.HipHeight = baseHip
	end
end
model:GetAttributeChangedSignal("Flying"):Connect(applyFlying)
applyFlying()

pcall(function()
	root:SetNetworkOwner(nil)
end)

local home = root.Position
local rng = Random.new()

local function wander()
	while model.Parent and hum.Health > 0 do
		if model:GetAttribute("Wander") then
			local r = model:GetAttribute("WanderRadius") or 40
			local target = home + Vector3.new(rng:NextNumber(-r, r), 0, rng:NextNumber(-r, r))
			local flying = canFly and rng:NextNumber() < 0.45
			if flying then
				API.SetFlying(model, true)
				API.Run(model, target)
			elseif rng:NextNumber() < 0.25 then
				API.Run(model, target)
			else
				API.Walk(model, target)
			end
			local done = false
			local conn = hum.MoveToFinished:Connect(function()
				done = true
			end)
			local t0 = os.clock()
			while not done and os.clock() - t0 < 10 and model:GetAttribute("Wander") do
				task.wait(0.2)
			end
			conn:Disconnect()
			hum:MoveTo(root.Position)
			if flying then
				API.SetFlying(model, false)
				task.wait(1)
			end
			task.wait(rng:NextNumber(1.5, 4))
			local roll = rng:NextNumber()
			if canFly and roll < 0.2 then
				API.Play(model, "Flap")
				task.wait(2)
			elseif roll < 0.3 then
				API.Play(model, "Roar")
				task.wait(2)
			elseif roll < 0.55 then
				API.Play(model, "Eat")
				task.wait(5)
			end
		else
			task.wait(1)
		end
	end
end

task.spawn(wander)
