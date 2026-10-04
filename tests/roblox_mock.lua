-- Mock mínimo de Vector3/CFrame/Instance para testar DinoRig.lua fora do Roblox.
local V = {}
V.__index = function(t, k)
	if k == "Magnitude" then
		return math.sqrt(t.X * t.X + t.Y * t.Y + t.Z * t.Z)
	end
	return V[k]
end
local function v3(x, y, z)
	return setmetatable({ X = x or 0, Y = y or 0, Z = z or 0 }, V)
end
V.__add = function(a, b) return v3(a.X + b.X, a.Y + b.Y, a.Z + b.Z) end
V.__sub = function(a, b) return v3(a.X - b.X, a.Y - b.Y, a.Z - b.Z) end
V.__unm = function(a) return v3(-a.X, -a.Y, -a.Z) end
V.__mul = function(a, b)
	if type(a) == "number" then a, b = b, a end
	return v3(a.X * b, a.Y * b, a.Z * b)
end
V.__div = function(a, b) return v3(a.X / b, a.Y / b, a.Z / b) end
function V.Dot(a, b) return a.X * b.X + a.Y * b.Y + a.Z * b.Z end
function V.Cross(a, b) return v3(a.Y * b.Z - a.Z * b.Y, a.Z * b.X - a.X * b.Z, a.X * b.Y - a.Y * b.X) end
Vector3 = { new = v3, zero = v3(0, 0, 0), xAxis = v3(1, 0, 0), yAxis = v3(0, 1, 0), zAxis = v3(0, 0, 1) }

local C = {}
local function cf(p, r) -- r = {{r00,r01,r02},{...},{...}}
	return setmetatable({ p = p, r = r }, C)
end
C.__index = function(t, k)
	if k == "Position" then return t.p end
	if k == "Rotation" then return cf(v3(), t.r) end
	return C[k]
end
local function rmul(a, b)
	local o = {}
	for i = 1, 3 do
		o[i] = {}
		for j = 1, 3 do
			o[i][j] = a[i][1] * b[1][j] + a[i][2] * b[2][j] + a[i][3] * b[3][j]
		end
	end
	return o
end
local function rvec(r, v)
	return v3(r[1][1] * v.X + r[1][2] * v.Y + r[1][3] * v.Z, r[2][1] * v.X + r[2][2] * v.Y + r[2][3] * v.Z,
		r[3][1] * v.X + r[3][2] * v.Y + r[3][3] * v.Z)
end
local function rT(r)
	return { { r[1][1], r[2][1], r[3][1] }, { r[1][2], r[2][2], r[3][2] }, { r[1][3], r[2][3], r[3][3] } }
end
C.__mul = function(a, b)
	if getmetatable(b) == V then
		return a.p + rvec(a.r, b)
	end
	return cf(a.p + rvec(a.r, b.p), rmul(a.r, b.r))
end
function C.Inverse(a)
	local t = rT(a.r)
	return cf(-rvec(t, a.p), t)
end
function C.VectorToWorldSpace(a, v) return rvec(a.r, v) end
function C.PointToObjectSpace(a, v) return rvec(rT(a.r), v - a.p) end
local I3 = { { 1, 0, 0 }, { 0, 1, 0 }, { 0, 0, 1 } }
CFrame = {
	new = function(...)
		local n = select("#", ...)
		local a = { ... }
		if n == 0 then return cf(v3(), I3) end
		if n == 1 then return cf(a[1], I3) end
		if n == 3 then return cf(v3(a[1], a[2], a[3]), I3) end
		return cf(v3(a[1], a[2], a[3]), { { a[4], a[5], a[6] }, { a[7], a[8], a[9] }, { a[10], a[11], a[12] } })
	end,
	fromMatrix = function(p, x, y, z)
		return cf(p, { { x.X, y.X, z.X }, { x.Y, y.Y, z.Y }, { x.Z, y.Z, z.Z } })
	end,
}
function C.components(a)
	return a.p.X, a.p.Y, a.p.Z, a.r[1][1], a.r[1][2], a.r[1][3], a.r[2][1], a.r[2][2], a.r[2][3], a.r[3][1], a.r[3][2], a.r[3][3]
end

-- Instances
local Inst = {}
local CLASS_ISA = { Bone = { Bone = true, Attachment = true }, Part = { Part = true, BasePart = true },
	MeshPart = { MeshPart = true, BasePart = true } }
Inst.__index = function(t, k)
	local raw = rawget(t, "_p")
	if k == "TransformedWorldCFrame" then
		local par = raw.Parent
		local pw = (par._p.Class == "Bone") and par.TransformedWorldCFrame or par.CFrame
		return pw * raw.CFrame * (raw.Transform or CFrame.new())
	end
	if raw[k] ~= nil then return raw[k] end
	if Inst[k] then return Inst[k] end
	for _, c in ipairs(raw._children) do
		if c.Name == k then return c end
	end
	return nil
end
Inst.__newindex = function(t, k, v)
	local raw = rawget(t, "_p")
	if k == "Parent" then
		local old = raw.Parent
		if old then
			local ch = old._p._children
			for i = #ch, 1, -1 do
				if ch[i] == t then table.remove(ch, i) end
			end
		end
		if v then table.insert(v._p._children, t) end
	end
	raw[k] = v
end
function Inst.IsA(t, c)
	local cls = t._p.Class
	return cls == c or (CLASS_ISA[cls] and CLASS_ISA[cls][c]) or false
end
function Inst.GetChildren(t)
	local o = {}
	for i, c in ipairs(t._p._children) do o[i] = c end
	return o
end
function Inst.GetDescendants(t)
	local o = {}
	local function rec(x)
		for _, c in ipairs(x._p._children) do
			table.insert(o, c)
			rec(c)
		end
	end
	rec(t)
	return o
end
function Inst.FindFirstChild(t, n)
	for _, c in ipairs(t._p._children) do
		if c.Name == n then return c end
	end
end
Inst.WaitForChild = Inst.FindFirstChild
function Inst.FindFirstChildOfClass(t, cls)
	for _, c in ipairs(t._p._children) do
		if c._p.Class == cls then return c end
	end
end
function Inst.IsDescendantOf(t, a)
	local p = t._p.Parent
	while p do
		if p == a then return true end
		p = p._p.Parent
	end
	return false
end
function Inst.GetAttribute(t, k) return t._p._attrs[k] end
function Inst.SetAttribute(t, k, v) t._p._attrs[k] = v end
function Inst.GetAttributes(t) return t._p._attrs end
function Inst.GetFullName(t) return t.Name end
Instance = {
	new = function(cls)
		return setmetatable({ _p = { Class = cls, Name = cls, _children = {}, _attrs = {} } }, Inst)
	end,
}
Enum = setmetatable({}, { __index = function() return setmetatable({}, { __index = function(_, k) return k end }) end })
warn = print
