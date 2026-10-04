--[[
	DinoAPI (ModuleScript) — gerado pelo dinomaker.

	local API = require(dino.DinoAPI)
	API.Play(dino, "Attack")   -- "Attack" | "Roar" | "Hit" | "Eat" | "Flap" (asas)
	API.Walk(dino, Vector3.new(10, 0, 0))
	API.Run(dino, Vector3.new(50, 0, 0))
	API.SetFlying(dino, true)  -- só dinos com asas
	API.Kill(dino)             -- toca "Death"
]]

local API = {}

function API.Play(model, action)
	model:SetAttribute("Action", action)
	model:SetAttribute("ActionNonce", (model:GetAttribute("ActionNonce") or 0) + 1)
end

function API.Walk(model, position)
	local hum = model:FindFirstChildOfClass("Humanoid")
	hum.WalkSpeed = model:GetAttribute("WalkSpeed") or 8
	hum:MoveTo(position)
end

function API.Run(model, position)
	local hum = model:FindFirstChildOfClass("Humanoid")
	hum.WalkSpeed = model:GetAttribute("RunSpeed") or 16
	hum:MoveTo(position)
end

function API.SetFlying(model, flying)
	model:SetAttribute("Flying", flying and true or false)
end

function API.Kill(model)
	local hum = model:FindFirstChildOfClass("Humanoid")
	hum.Health = 0
end

return API
