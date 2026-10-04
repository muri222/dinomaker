--[[
	DinoRig (ModuleScript) — kit da versão B (mesh importada pelo Import 3D).

	O importador pode girar/escalar o modelo e orientar os ossos do jeito dele.
	Por isso nada aqui assume orientação: no setup comparamos a posição de descanso
	dos ossos importados com a do gerador (DinoRigData) e achamos a melhor
	rotação (24 rotações de eixo) + escala + translação. As animações são aplicadas
	como "deltas" no espaço do gerador e convertidas para cada Bone.Transform.
]]

local Data = require(script.Parent:WaitForChild("DinoRigData"))

local Rig = {}

local IDENT = CFrame.new()

local function cf(t)
	return CFrame.new(t[1], t[2], t[3], t[4], t[5], t[6], t[7], t[8], t[9], t[10], t[11], t[12])
end

local REST, REST_INV, OFF = {}, {}, {}
for _, b in ipairs(Data.bones) do
	REST[b.name] = cf(b.rest)
	REST_INV[b.name] = REST[b.name]:Inverse()
end
for _, b in ipairs(Data.bones) do
	if b.parent then
		OFF[b.name] = REST_INV[b.parent] * REST[b.name]
	end
end

local function norm(name)
	name = string.lower(name)
	name = string.gsub(name, "^.*[:|]", "")
	return name
end

-- Bones do modelo importado, indexados pelo nome do gerador
function Rig.findBones(model, kit)
	local wanted = {}
	for _, b in ipairs(Data.bones) do
		wanted[norm(b.name)] = b.name
	end
	local out, n = {}, 0
	for _, d in ipairs(model:GetDescendants()) do
		if d:IsA("Bone") and not (kit and d:IsDescendantOf(kit)) then
			local key = wanted[norm(d.Name)]
			if key and not out[key] then
				out[key] = d
				n = n + 1
			end
		end
	end
	return out, n
end

-- Acha o modelo do dino: o pai do kit, ou (kit solto) o Model com mais ossos que batem
function Rig.findTarget(kit)
	local p = kit.Parent
	if p and p:IsA("Model") then
		return p
	end
	-- vários dinos no mapa: escolhe o esqueleto que ENCAIXA melhor neste kit
	-- (proporções iguais às do gerador), ignorando modelos que já têm kit
	local best, bestScore = nil, math.huge
	for _, m in ipairs(workspace:GetDescendants()) do
		if m:IsA("Model") and not m:FindFirstChild("DinoKit") then
			local bones, n = Rig.findBones(m, kit)
			if n >= 3 then
				local fit = Rig.fit(bones)
				if fit then
					local score = fit.err + (#Data.bones - n) * 0.5
					if score < bestScore then
						best, bestScore = m, score
					end
				end
			end
		end
	end
	if best and bestScore < 2 then
		kit.Parent = best
		return best
	end
	return nil
end

local function rotations()
	local axes = { Vector3.xAxis, Vector3.yAxis, Vector3.zAxis }
	local out = {}
	for i = 1, 3 do
		for j = 1, 3 do
			if i ~= j then
				for _, si in ipairs({ 1, -1 }) do
					for _, sj in ipairs({ 1, -1 }) do
						local x = axes[i] * si
						local y = axes[j] * sj
						table.insert(out, CFrame.fromMatrix(Vector3.zero, x, y, x:Cross(y)))
					end
				end
			end
		end
	end
	return out
end

-- Melhor similaridade (R, k, t) levando posições do gerador -> mundo
function Rig.fit(bones)
	local P, Q = {}, {}
	for _, b in ipairs(Data.bones) do
		local bone = bones[b.name]
		if bone then
			table.insert(P, REST[b.name].Position)
			table.insert(Q, bone.TransformedWorldCFrame.Position)
		end
	end
	local n = #P
	if n < 3 then
		return nil
	end
	local a, c = Vector3.zero, Vector3.zero
	for i = 1, n do
		a = a + P[i]
		c = c + Q[i]
	end
	a = a / n
	c = c / n
	local best, bestErr
	for _, R in ipairs(rotations()) do
		local num, den = 0, 0
		for i = 1, n do
			local p = R:VectorToWorldSpace(P[i] - a)
			num = num + p:Dot(Q[i] - c)
			den = den + p:Dot(p)
		end
		local k = den > 0 and num / den or 0
		if k > 0 then
			local err = 0
			for i = 1, n do
				local d = R:VectorToWorldSpace(P[i] - a) * k - (Q[i] - c)
				err = err + d:Dot(d)
			end
			if not bestErr or err < bestErr then
				bestErr = err
				best = { R = R, k = k, t = c - R:VectorToWorldSpace(a) * k }
			end
		end
	end
	if best then
		best.err = math.sqrt(bestErr / n) / best.k
		best.n = n
	end
	return best
end

-- Servidor: cria HumanoidRootPart/Humanoid, solda, move os VFX e grava o mapa
function Rig.setup(model, kit)
	if not model or not model:IsA("Model") or model == workspace then
		warn("[DinoKit] A pasta DinoKit precisa estar dentro do modelo importado do dino.")
		return false
	end
	if model:GetAttribute("DinoReady") then
		return true
	end
	local bones, count = Rig.findBones(model, kit)
	local fit = Rig.fit(bones)
	if not fit then
		warn("[DinoKit] Não achei os ossos do dino em", model:GetFullName(), "- importe o FBX com o rig (Rig General).")
		return false
	end
	if fit.err > 0.5 then
		warn(string.format("[DinoKit] Encaixe aproximado (erro %.2f px, %d ossos). Confira se este kit é deste dino.", fit.err, fit.n))
	end
	local R, k, t = fit.R, fit.k, fit.t
	local function mapFrame(F)
		return CFrame.new(t + R:VectorToWorldSpace(F.Position) * k) * (R * F.Rotation)
	end

	local hrp = model:FindFirstChild("HumanoidRootPart")
	if not hrp then
		hrp = Instance.new("Part")
		hrp.Name = "HumanoidRootPart"
		hrp.Size = Vector3.new(Data.hrp.size[1], Data.hrp.size[2], Data.hrp.size[3]) * k
		hrp.Transparency = 1
		hrp.CanCollide = true
		hrp.CFrame = mapFrame(cf(Data.hrp.cf))
		hrp.Parent = model
	end
	for _, p in ipairs(model:GetDescendants()) do
		if p:IsA("BasePart") and p ~= hrp then
			local w = Instance.new("WeldConstraint")
			w.Part0 = hrp
			w.Part1 = p
			w.Parent = hrp
			p.Anchored = false
			p.CanCollide = false
			p.CanQuery = false
			p.Massless = true
		end
	end
	hrp.Anchored = false
	model.PrimaryPart = hrp

	local hum = model:FindFirstChildOfClass("Humanoid")
	if not hum then
		hum = Instance.new("Humanoid")
		hum.RigType = Enum.HumanoidRigType.R15
		hum.RequiresNeck = false
		hum.BreakJointsOnDeath = false
		hum.DisplayDistanceType = Enum.HumanoidDisplayDistanceType.None
		Instance.new("Animator").Parent = hum
		hum.Parent = model
	end
	hum.HipHeight = Data.hipHeight * k

	for key, v in pairs(kit:GetAttributes()) do
		if model:GetAttribute(key) == nil then
			model:SetAttribute(key, v)
		end
	end
	model:SetAttribute("WalkSpeed", Data.walkSpeed * k)
	model:SetAttribute("RunSpeed", Data.runSpeed * k)
	hum.WalkSpeed = Data.walkSpeed * k

	-- VFX: Attachments do kit vão para os ossos certos
	local vfx = kit:FindFirstChild("VFX")
	if vfx then
		for _, att in ipairs(vfx:GetChildren()) do
			local bone = bones[att:GetAttribute("Bone") or ""]
			if att:IsA("Attachment") and bone then
				local W = mapFrame(att.CFrame)
				att.Parent = bone
				att.CFrame = bone.TransformedWorldCFrame:Inverse() * W
			end
		end
	end

	local H = hrp.CFrame
	model:SetAttribute("DinoMapR", H.Rotation:Inverse() * R)
	model:SetAttribute("DinoMapT", H:PointToObjectSpace(t))
	model:SetAttribute("DinoMapK", k)
	model:SetAttribute("DinoReady", true)
	return true
end

-- Cliente: driver que converte poses do gerador em Bone.Transform
function Rig.newDriver(model, root, kit)
	local bones = Rig.findBones(model, kit)
	local mapR = model:GetAttribute("DinoMapR") or IDENT
	local mapT = model:GetAttribute("DinoMapT") or Vector3.zero
	local k = model:GetAttribute("DinoMapK") or 1
	local H0inv = root.CFrame:Inverse()
	local restH = {}
	for name, bone in pairs(bones) do
		bone.Transform = IDENT
		restH[name] = H0inv * bone.TransformedWorldCFrame
	end

	local driver = {}
	function driver.has(name)
		return REST[name] ~= nil
	end
	function driver.apply(pose)
		local H = root.CFrame
		local Rw = H.Rotation * mapR
		local Rinv = Rw:Inverse()
		local tw = H * mapT
		local J, desired = {}, {}
		for _, b in ipairs(Data.bones) do
			local L = pose[b.name] or IDENT
			local Jw
			if b.parent then
				Jw = J[b.parent] * OFF[b.name] * L
			else
				Jw = REST[b.name] * L
			end
			J[b.name] = Jw
			local bone = bones[b.name]
			if bone then
				local D = Jw * REST_INV[b.name]
				local Rr = Rw * D.Rotation * Rinv
				local pos = tw + Rw:VectorToWorldSpace(D.Position) * k - Rr:VectorToWorldSpace(tw)
				local want = CFrame.new(pos) * Rr * (H * restH[b.name])
				desired[bone] = want
				local parent = bone.Parent
				local pw
				if parent:IsA("Bone") then
					pw = desired[parent] or parent.TransformedWorldCFrame
				else
					pw = parent.CFrame
				end
				bone.Transform = (pw * bone.CFrame):Inverse() * want
			end
		end
	end
	return driver
end

return Rig
