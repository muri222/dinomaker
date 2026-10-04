--[[
	DinoBrain (Script, RunContext = Server) — gerado pelo dinomaker.

	Atributos do Model (editáveis no Studio):
	  WalkSpeed / RunSpeed  velocidades que batem com a passada da animação
	  Wander (bool)         passeia sozinho perto do ponto inicial (teste rápido)
	  WanderRadius          raio do passeio
	  Action / ActionNonce  dispara ações (use DinoAPI.Play)
	  Flying (bool)         toca a animação Fly (dinos com asas)
]]

local model = script.Parent
local hum = model:WaitForChild("Humanoid")
local root = model:WaitForChild("HumanoidRootPart")
local API = require(model:WaitForChild("DinoAPI"))

hum.WalkSpeed = model:GetAttribute("WalkSpeed") or hum.WalkSpeed

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
			if rng:NextNumber() < 0.25 then
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
			task.wait(rng:NextNumber(1.5, 4))
			local roll = rng:NextNumber()
			if roll < 0.3 then
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
