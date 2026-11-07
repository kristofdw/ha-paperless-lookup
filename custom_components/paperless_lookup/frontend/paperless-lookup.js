// node_modules/@lit/reactive-element/css-tag.js
var e = globalThis, t = e.ShadowRoot && (e.ShadyCSS === void 0 || e.ShadyCSS.nativeShadow) && "adoptedStyleSheets" in Document.prototype && "replace" in CSSStyleSheet.prototype, n = Symbol(), r = /* @__PURE__ */ new WeakMap(), i = class {
	constructor(e, t, r) {
		if (this._$cssResult$ = !0, r !== n) throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");
		this.cssText = e, this.t = t;
	}
	get styleSheet() {
		let e = this.o, n = this.t;
		if (t && e === void 0) {
			let t = n !== void 0 && n.length === 1;
			t && (e = r.get(n)), e === void 0 && ((this.o = e = new CSSStyleSheet()).replaceSync(this.cssText), t && r.set(n, e));
		}
		return e;
	}
	toString() {
		return this.cssText;
	}
}, a = (e) => new i(typeof e == "string" ? e : e + "", void 0, n), o = (e, ...t) => new i(e.length === 1 ? e[0] : t.reduce((t, n, r) => t + ((e) => {
	if (!0 === e._$cssResult$) return e.cssText;
	if (typeof e == "number") return e;
	throw Error("Value passed to 'css' function must be a 'css' function result: " + e + ". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.");
})(n) + e[r + 1], e[0]), e, n), s = (n, r) => {
	if (t) n.adoptedStyleSheets = r.map((e) => e instanceof CSSStyleSheet ? e : e.styleSheet);
	else for (let t of r) {
		let r = document.createElement("style"), i = e.litNonce;
		i !== void 0 && r.setAttribute("nonce", i), r.textContent = t.cssText, n.appendChild(r);
	}
}, c = t ? (e) => e : (e) => e instanceof CSSStyleSheet ? ((e) => {
	let t = "";
	for (let n of e.cssRules) t += n.cssText;
	return a(t);
})(e) : e, { is: l, defineProperty: u, getOwnPropertyDescriptor: d, getOwnPropertyNames: ee, getOwnPropertySymbols: te, getPrototypeOf: ne } = Object, f = globalThis, re = f.trustedTypes, ie = re ? re.emptyScript : "", ae = f.reactiveElementPolyfillSupport, p = (e, t) => e, m = {
	toAttribute(e, t) {
		switch (t) {
			case Boolean:
				e = e ? ie : null;
				break;
			case Object:
			case Array: e = e == null ? e : JSON.stringify(e);
		}
		return e;
	},
	fromAttribute(e, t) {
		let n = e;
		switch (t) {
			case Boolean:
				n = e !== null;
				break;
			case Number:
				n = e === null ? null : Number(e);
				break;
			case Object:
			case Array: try {
				n = JSON.parse(e);
			} catch {
				n = null;
			}
		}
		return n;
	}
}, h = (e, t) => !l(e, t), g = {
	attribute: !0,
	type: String,
	converter: m,
	reflect: !1,
	useDefault: !1,
	hasChanged: h
};
Symbol.metadata ??= Symbol("metadata"), f.litPropertyMetadata ??= /* @__PURE__ */ new WeakMap();
var _ = class extends HTMLElement {
	static addInitializer(e) {
		this._$Ei(), (this.l ??= []).push(e);
	}
	static get observedAttributes() {
		return this.finalize(), this._$Eh && [...this._$Eh.keys()];
	}
	static createProperty(e, t = g) {
		if (t.state && (t.attribute = !1), this._$Ei(), this.prototype.hasOwnProperty(e) && ((t = Object.create(t)).wrapped = !0), this.elementProperties.set(e, t), !t.noAccessor) {
			let n = Symbol(), r = this.getPropertyDescriptor(e, n, t);
			r !== void 0 && u(this.prototype, e, r);
		}
	}
	static getPropertyDescriptor(e, t, n) {
		let { get: r, set: i } = d(this.prototype, e) ?? {
			get() {
				return this[t];
			},
			set(e) {
				this[t] = e;
			}
		};
		return {
			get: r,
			set(t) {
				let a = r?.call(this);
				i?.call(this, t), this.requestUpdate(e, a, n);
			},
			configurable: !0,
			enumerable: !0
		};
	}
	static getPropertyOptions(e) {
		return this.elementProperties.get(e) ?? g;
	}
	static _$Ei() {
		if (this.hasOwnProperty(p("elementProperties"))) return;
		let e = ne(this);
		e.finalize(), e.l !== void 0 && (this.l = [...e.l]), this.elementProperties = new Map(e.elementProperties);
	}
	static finalize() {
		if (this.hasOwnProperty(p("finalized"))) return;
		if (this.finalized = !0, this._$Ei(), this.hasOwnProperty(p("properties"))) {
			let e = this.properties, t = [...ee(e), ...te(e)];
			for (let n of t) this.createProperty(n, e[n]);
		}
		let e = this[Symbol.metadata];
		if (e !== null) {
			let t = litPropertyMetadata.get(e);
			if (t !== void 0) for (let [e, n] of t) this.elementProperties.set(e, n);
		}
		this._$Eh = /* @__PURE__ */ new Map();
		for (let [e, t] of this.elementProperties) {
			let n = this._$Eu(e, t);
			n !== void 0 && this._$Eh.set(n, e);
		}
		this.elementStyles = this.finalizeStyles(this.styles);
	}
	static finalizeStyles(e) {
		let t = [];
		if (Array.isArray(e)) {
			let n = new Set(e.flat(1 / 0).reverse());
			for (let e of n) t.unshift(c(e));
		} else e !== void 0 && t.push(c(e));
		return t;
	}
	static _$Eu(e, t) {
		let n = t.attribute;
		return !1 === n ? void 0 : typeof n == "string" ? n : typeof e == "string" ? e.toLowerCase() : void 0;
	}
	constructor() {
		super(), this._$Ep = void 0, this.isUpdatePending = !1, this.hasUpdated = !1, this._$Em = null, this._$Ev();
	}
	_$Ev() {
		this._$ES = new Promise((e) => this.enableUpdating = e), this._$AL = /* @__PURE__ */ new Map(), this._$E_(), this.requestUpdate(), this.constructor.l?.forEach((e) => e(this));
	}
	addController(e) {
		(this._$EO ??= /* @__PURE__ */ new Set()).add(e), this.renderRoot !== void 0 && this.isConnected && e.hostConnected?.();
	}
	removeController(e) {
		this._$EO?.delete(e);
	}
	_$E_() {
		let e = /* @__PURE__ */ new Map(), t = this.constructor.elementProperties;
		for (let n of t.keys()) this.hasOwnProperty(n) && (e.set(n, this[n]), delete this[n]);
		e.size > 0 && (this._$Ep = e);
	}
	createRenderRoot() {
		let e = this.shadowRoot ?? this.attachShadow(this.constructor.shadowRootOptions);
		return s(e, this.constructor.elementStyles), e;
	}
	connectedCallback() {
		this.renderRoot ??= this.createRenderRoot(), this.enableUpdating(!0), this._$EO?.forEach((e) => e.hostConnected?.());
	}
	enableUpdating(e) {}
	disconnectedCallback() {
		this._$EO?.forEach((e) => e.hostDisconnected?.());
	}
	attributeChangedCallback(e, t, n) {
		this._$AK(e, n);
	}
	_$ET(e, t) {
		let n = this.constructor.elementProperties.get(e), r = this.constructor._$Eu(e, n);
		if (r !== void 0 && !0 === n.reflect) {
			let i = (n.converter?.toAttribute === void 0 ? m : n.converter).toAttribute(t, n.type);
			this._$Em = e, i == null ? this.removeAttribute(r) : this.setAttribute(r, i), this._$Em = null;
		}
	}
	_$AK(e, t) {
		let n = this.constructor, r = n._$Eh.get(e);
		if (r !== void 0 && this._$Em !== r) {
			let e = n.getPropertyOptions(r), i = typeof e.converter == "function" ? { fromAttribute: e.converter } : e.converter?.fromAttribute === void 0 ? m : e.converter;
			this._$Em = r;
			let a = i.fromAttribute(t, e.type);
			this[r] = a ?? this._$Ej?.get(r) ?? a, this._$Em = null;
		}
	}
	requestUpdate(e, t, n, r = !1, i) {
		if (e !== void 0) {
			let a = this.constructor;
			if (!1 === r && (i = this[e]), n ??= a.getPropertyOptions(e), !((n.hasChanged ?? h)(i, t) || n.useDefault && n.reflect && i === this._$Ej?.get(e) && !this.hasAttribute(a._$Eu(e, n)))) return;
			this.C(e, t, n);
		}
		!1 === this.isUpdatePending && (this._$ES = this._$EP());
	}
	C(e, t, { useDefault: n, reflect: r, wrapped: i }, a) {
		n && !(this._$Ej ??= /* @__PURE__ */ new Map()).has(e) && (this._$Ej.set(e, a ?? t ?? this[e]), !0 !== i || a !== void 0) || (this._$AL.has(e) || (this.hasUpdated || n || (t = void 0), this._$AL.set(e, t)), !0 === r && this._$Em !== e && (this._$Eq ??= /* @__PURE__ */ new Set()).add(e));
	}
	async _$EP() {
		this.isUpdatePending = !0;
		try {
			await this._$ES;
		} catch (e) {
			Promise.reject(e);
		}
		let e = this.scheduleUpdate();
		return e != null && await e, !this.isUpdatePending;
	}
	scheduleUpdate() {
		return this.performUpdate();
	}
	performUpdate() {
		if (!this.isUpdatePending) return;
		if (!this.hasUpdated) {
			if (this.renderRoot ??= this.createRenderRoot(), this._$Ep) {
				for (let [e, t] of this._$Ep) this[e] = t;
				this._$Ep = void 0;
			}
			let e = this.constructor.elementProperties;
			if (e.size > 0) for (let [t, n] of e) {
				let { wrapped: e } = n, r = this[t];
				!0 !== e || this._$AL.has(t) || r === void 0 || this.C(t, void 0, n, r);
			}
		}
		let e = !1, t = this._$AL;
		try {
			e = this.shouldUpdate(t), e ? (this.willUpdate(t), this._$EO?.forEach((e) => e.hostUpdate?.()), this.update(t)) : this._$EM();
		} catch (t) {
			throw e = !1, this._$EM(), t;
		}
		e && this._$AE(t);
	}
	willUpdate(e) {}
	_$AE(e) {
		this._$EO?.forEach((e) => e.hostUpdated?.()), this.hasUpdated || (this.hasUpdated = !0, this.firstUpdated(e)), this.updated(e);
	}
	_$EM() {
		this._$AL = /* @__PURE__ */ new Map(), this.isUpdatePending = !1;
	}
	get updateComplete() {
		return this.getUpdateComplete();
	}
	getUpdateComplete() {
		return this._$ES;
	}
	shouldUpdate(e) {
		return !0;
	}
	update(e) {
		this._$Eq &&= this._$Eq.forEach((e) => this._$ET(e, this[e])), this._$EM();
	}
	updated(e) {}
	firstUpdated(e) {}
};
_.elementStyles = [], _.shadowRootOptions = { mode: "open" }, _[p("elementProperties")] = /* @__PURE__ */ new Map(), _[p("finalized")] = /* @__PURE__ */ new Map(), ae?.({ ReactiveElement: _ }), (f.reactiveElementVersions ??= []).push("2.1.2");
// node_modules/lit-html/lit-html.js
var v = globalThis, y = (e) => e, b = v.trustedTypes, x = b ? b.createPolicy("lit-html", { createHTML: (e) => e }) : void 0, S = "$lit$", C = `lit$${Math.random().toFixed(9).slice(2)}$`, w = "?" + C, oe = `<${w}>`, T = document, E = () => T.createComment(""), D = (e) => e === null || typeof e != "object" && typeof e != "function", O = Array.isArray, se = (e) => O(e) || typeof e?.[Symbol.iterator] == "function", k = "[ 	\n\f\r]", A = /<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g, j = /-->/g, M = />/g, N = RegExp(`>|${k}(?:([^\\s"'>=/]+)(${k}*=${k}*(?:[^ \t\n\f\r"'\`<>=]|("|')|))|$)`, "g"), ce = /'/g, le = /"/g, ue = /^(?:script|style|textarea|title)$/i, P = ((e) => (t, ...n) => ({
	_$litType$: e,
	strings: t,
	values: n
}))(1), F = Symbol.for("lit-noChange"), I = Symbol.for("lit-nothing"), L = /* @__PURE__ */ new WeakMap(), R = T.createTreeWalker(T, 129);
function z(e, t) {
	if (!O(e) || !e.hasOwnProperty("raw")) throw Error("invalid template strings array");
	return x === void 0 ? t : x.createHTML(t);
}
var de = (e, t) => {
	let n = e.length - 1, r = [], i, a = t === 2 ? "<svg>" : t === 3 ? "<math>" : "", o = A;
	for (let t = 0; t < n; t++) {
		let n = e[t], s, c, l = -1, u = 0;
		for (; u < n.length && (o.lastIndex = u, c = o.exec(n), c !== null);) u = o.lastIndex, o === A ? c[1] === "!--" ? o = j : c[1] === void 0 ? c[2] === void 0 ? c[3] !== void 0 && (o = N) : (ue.test(c[2]) && (i = RegExp("</" + c[2], "g")), o = N) : o = M : o === N ? c[0] === ">" ? (o = i ?? A, l = -1) : c[1] === void 0 ? l = -2 : (l = o.lastIndex - c[2].length, s = c[1], o = c[3] === void 0 ? N : c[3] === "\"" ? le : ce) : o === le || o === ce ? o = N : o === j || o === M ? o = A : (o = N, i = void 0);
		let d = o === N && e[t + 1].startsWith("/>") ? " " : "";
		a += o === A ? n + oe : l >= 0 ? (r.push(s), n.slice(0, l) + S + n.slice(l) + C + d) : n + C + (l === -2 ? t : d);
	}
	return [z(e, a + (e[n] || "<?>") + (t === 2 ? "</svg>" : t === 3 ? "</math>" : "")), r];
}, B = class e {
	constructor({ strings: t, _$litType$: n }, r) {
		let i;
		this.parts = [];
		let a = 0, o = 0, s = t.length - 1, c = this.parts, [l, u] = de(t, n);
		if (this.el = e.createElement(l, r), R.currentNode = this.el.content, n === 2 || n === 3) {
			let e = this.el.content.firstChild;
			e.replaceWith(...e.childNodes);
		}
		for (; (i = R.nextNode()) !== null && c.length < s;) {
			if (i.nodeType === 1) {
				if (i.hasAttributes()) for (let e of i.getAttributeNames()) if (e.endsWith(S)) {
					let t = u[o++], n = i.getAttribute(e).split(C), r = /([.?@])?(.*)/.exec(t);
					c.push({
						type: 1,
						index: a,
						name: r[2],
						strings: n,
						ctor: r[1] === "." ? pe : r[1] === "?" ? me : r[1] === "@" ? he : U
					}), i.removeAttribute(e);
				} else e.startsWith(C) && (c.push({
					type: 6,
					index: a
				}), i.removeAttribute(e));
				if (ue.test(i.tagName)) {
					let e = i.textContent.split(C), t = e.length - 1;
					if (t > 0) {
						i.textContent = b ? b.emptyScript : "";
						for (let n = 0; n < t; n++) i.append(e[n], E()), R.nextNode(), c.push({
							type: 2,
							index: ++a
						});
						i.append(e[t], E());
					}
				}
			} else if (i.nodeType === 8) {
				if (i.data === w) c.push({
					type: 2,
					index: a
				});
				else {
					let e = -1;
					for (; (e = i.data.indexOf(C, e + 1)) !== -1;) c.push({
						type: 7,
						index: a
					}), e += C.length - 1;
				}
			}
			a++;
		}
	}
	static createElement(e, t) {
		let n = T.createElement("template");
		return n.innerHTML = e, n;
	}
};
function V(e, t, n = e, r) {
	if (t === F) return t;
	let i = r === void 0 ? n._$Cl : n._$Co?.[r], a = D(t) ? void 0 : t._$litDirective$;
	return i?.constructor !== a && (i?._$AO?.(!1), a === void 0 ? i = void 0 : (i = new a(e), i._$AT(e, n, r)), r === void 0 ? n._$Cl = i : (n._$Co ??= [])[r] = i), i !== void 0 && (t = V(e, i._$AS(e, t.values), i, r)), t;
}
var fe = class {
	constructor(e, t) {
		this._$AV = [], this._$AN = void 0, this._$AD = e, this._$AM = t;
	}
	get parentNode() {
		return this._$AM.parentNode;
	}
	get _$AU() {
		return this._$AM._$AU;
	}
	u(e) {
		let { el: { content: t }, parts: n } = this._$AD, r = (e?.creationScope ?? T).importNode(t, !0);
		R.currentNode = r;
		let i = R.nextNode(), a = 0, o = 0, s = n[0];
		for (; s !== void 0;) {
			if (a === s.index) {
				let t;
				s.type === 2 ? t = new H(i, i.nextSibling, this, e) : s.type === 1 ? t = new s.ctor(i, s.name, s.strings, this, e) : s.type === 6 && (t = new ge(i, this, e)), this._$AV.push(t), s = n[++o];
			}
			a !== s?.index && (i = R.nextNode(), a++);
		}
		return R.currentNode = T, r;
	}
	p(e) {
		let t = 0;
		for (let n of this._$AV) n !== void 0 && (n.strings === void 0 ? n._$AI(e[t]) : (n._$AI(e, n, t), t += n.strings.length - 2)), t++;
	}
}, H = class e {
	get _$AU() {
		return this._$AM?._$AU ?? this._$Cv;
	}
	constructor(e, t, n, r) {
		this.type = 2, this._$AH = I, this._$AN = void 0, this._$AA = e, this._$AB = t, this._$AM = n, this.options = r, this._$Cv = r?.isConnected ?? !0;
	}
	get parentNode() {
		let e = this._$AA.parentNode, t = this._$AM;
		return t !== void 0 && e?.nodeType === 11 && (e = t.parentNode), e;
	}
	get startNode() {
		return this._$AA;
	}
	get endNode() {
		return this._$AB;
	}
	_$AI(e, t = this) {
		e = V(this, e, t), D(e) ? e === I || e == null || e === "" ? (this._$AH !== I && this._$AR(), this._$AH = I) : e !== this._$AH && e !== F && this._(e) : e._$litType$ === void 0 ? e.nodeType === void 0 ? se(e) ? this.k(e) : this._(e) : this.T(e) : this.$(e);
	}
	O(e) {
		return this._$AA.parentNode.insertBefore(e, this._$AB);
	}
	T(e) {
		this._$AH !== e && (this._$AR(), this._$AH = this.O(e));
	}
	_(e) {
		this._$AH !== I && D(this._$AH) ? this._$AA.nextSibling.data = e : this.T(T.createTextNode(e)), this._$AH = e;
	}
	$(e) {
		let { values: t, _$litType$: n } = e, r = typeof n == "number" ? this._$AC(e) : (n.el === void 0 && (n.el = B.createElement(z(n.h, n.h[0]), this.options)), n);
		if (this._$AH?._$AD === r) this._$AH.p(t);
		else {
			let e = new fe(r, this), n = e.u(this.options);
			e.p(t), this.T(n), this._$AH = e;
		}
	}
	_$AC(e) {
		let t = L.get(e.strings);
		return t === void 0 && L.set(e.strings, t = new B(e)), t;
	}
	k(t) {
		O(this._$AH) || (this._$AH = [], this._$AR());
		let n = this._$AH, r, i = 0;
		for (let a of t) i === n.length ? n.push(r = new e(this.O(E()), this.O(E()), this, this.options)) : r = n[i], r._$AI(a), i++;
		i < n.length && (this._$AR(r && r._$AB.nextSibling, i), n.length = i);
	}
	_$AR(e = this._$AA.nextSibling, t) {
		for (this._$AP?.(!1, !0, t); e !== this._$AB;) {
			let t = y(e).nextSibling;
			y(e).remove(), e = t;
		}
	}
	setConnected(e) {
		this._$AM === void 0 && (this._$Cv = e, this._$AP?.(e));
	}
}, U = class {
	get tagName() {
		return this.element.tagName;
	}
	get _$AU() {
		return this._$AM._$AU;
	}
	constructor(e, t, n, r, i) {
		this.type = 1, this._$AH = I, this._$AN = void 0, this.element = e, this.name = t, this._$AM = r, this.options = i, n.length > 2 || n[0] !== "" || n[1] !== "" ? (this._$AH = Array(n.length - 1).fill(/* @__PURE__ */ new String()), this.strings = n) : this._$AH = I;
	}
	_$AI(e, t = this, n, r) {
		let i = this.strings, a = !1;
		if (i === void 0) e = V(this, e, t, 0), a = !D(e) || e !== this._$AH && e !== F, a && (this._$AH = e);
		else {
			let r = e, o, s;
			for (e = i[0], o = 0; o < i.length - 1; o++) s = V(this, r[n + o], t, o), s === F && (s = this._$AH[o]), a ||= !D(s) || s !== this._$AH[o], s === I ? e = I : e !== I && (e += (s ?? "") + i[o + 1]), this._$AH[o] = s;
		}
		a && !r && this.j(e);
	}
	j(e) {
		e === I ? this.element.removeAttribute(this.name) : this.element.setAttribute(this.name, e ?? "");
	}
}, pe = class extends U {
	constructor() {
		super(...arguments), this.type = 3;
	}
	j(e) {
		this.element[this.name] = e === I ? void 0 : e;
	}
}, me = class extends U {
	constructor() {
		super(...arguments), this.type = 4;
	}
	j(e) {
		this.element.toggleAttribute(this.name, !!e && e !== I);
	}
}, he = class extends U {
	constructor(e, t, n, r, i) {
		super(e, t, n, r, i), this.type = 5;
	}
	_$AI(e, t = this) {
		if ((e = V(this, e, t, 0) ?? I) === F) return;
		let n = this._$AH, r = e === I && n !== I || e.capture !== n.capture || e.once !== n.once || e.passive !== n.passive, i = e !== I && (n === I || r);
		r && this.element.removeEventListener(this.name, this, n), i && this.element.addEventListener(this.name, this, e), this._$AH = e;
	}
	handleEvent(e) {
		typeof this._$AH == "function" ? this._$AH.call(this.options?.host ?? this.element, e) : this._$AH.handleEvent(e);
	}
}, ge = class {
	constructor(e, t, n) {
		this.element = e, this.type = 6, this._$AN = void 0, this._$AM = t, this.options = n;
	}
	get _$AU() {
		return this._$AM._$AU;
	}
	_$AI(e) {
		V(this, e);
	}
}, _e = v.litHtmlPolyfillSupport;
_e?.(B, H), (v.litHtmlVersions ??= []).push("3.3.3");
var ve = (e, t, n) => {
	let r = n?.renderBefore ?? t, i = r._$litPart$;
	if (i === void 0) {
		let e = n?.renderBefore ?? null;
		r._$litPart$ = i = new H(t.insertBefore(E(), e), e, void 0, n ?? {});
	}
	return i._$AI(e), i;
}, W = globalThis, G = class extends _ {
	constructor() {
		super(...arguments), this.renderOptions = { host: this }, this._$Do = void 0;
	}
	createRenderRoot() {
		let e = super.createRenderRoot();
		return this.renderOptions.renderBefore ??= e.firstChild, e;
	}
	update(e) {
		let t = this.render();
		this.hasUpdated || (this.renderOptions.isConnected = this.isConnected), super.update(e), this._$Do = ve(t, this.renderRoot, this.renderOptions);
	}
	connectedCallback() {
		super.connectedCallback(), this._$Do?.setConnected(!0);
	}
	disconnectedCallback() {
		super.disconnectedCallback(), this._$Do?.setConnected(!1);
	}
	render() {
		return F;
	}
};
G._$litElement$ = !0, G.finalized = !0, W.litElementHydrateSupport?.({ LitElement: G });
var ye = W.litElementPolyfillSupport;
ye?.({ LitElement: G }), (W.litElementVersions ??= []).push("4.2.2");
// src/api.ts
var K = "paperless_lookup", be = (e) => e.callWS({ type: `${K}/access` }), xe = (e) => e.callWS({ type: `${K}/filters` }), q = (e, t) => e.callWS({
	type: `${K}/search`,
	...t
}), Se = (e, t) => e.callWS({
	type: `${K}/device_documents`,
	device_id: t
}), Ce = (e, t) => e.callWS({
	type: `${K}/area_documents`,
	area_id: t
}), we = (e) => e.callWS({ type: `${K}/devices_without_manual` }), Te = (e, t, n) => e.callWS({
	type: `${K}/link`,
	device_id: t,
	document_id: n
}), Ee = (e, t, n) => e.callWS({
	type: `${K}/unlink`,
	device_id: t,
	document_id: n
}), De = (e, t, n) => e.callWS({
	type: `${K}/ignore`,
	device_id: t,
	ignored: n
}), J = async (e, t, n) => {
	if (t.length === 0) return {};
	let r = await e.callWS({
		type: `${K}/sign_documents`,
		document_ids: t,
		kind: n
	}), i = {};
	for (let [e, t] of Object.entries(r.paths)) i[Number(e)] = t;
	return i;
}, Oe = (e) => typeof e == "object" && e && "code" in e ? String(e.code) : void 0, ke = () => ({
	query: "",
	categories: [],
	correspondent: null,
	dateFrom: "",
	dateTo: "",
	page: 1
}), Y = /^\d{4}-\d{2}-\d{2}$/, Ae = (e) => {
	let t = {
		query: e.query.trim().slice(0, 200),
		page: e.page,
		page_size: 25
	};
	return e.categories.length && (t.categories = [...e.categories].sort((e, t) => e - t)), e.correspondent !== null && (t.correspondents = [e.correspondent]), Y.test(e.dateFrom) && (t.date_from = e.dateFrom), Y.test(e.dateTo) && (t.date_to = e.dateTo), t;
}, je = (e, t) => e.includes(t) ? e.filter((e) => e !== t) : [...e, t], Me = (e, t) => {
	if (!e || !Y.test(e)) return "";
	let [n, r, i] = e.split("-").map(Number);
	return new Intl.DateTimeFormat(t, {
		year: "numeric",
		month: "short",
		day: "numeric",
		timeZone: "UTC"
	}).format(new Date(Date.UTC(n, r - 1, i)));
}, Ne = (e) => e ? e === "application/pdf" ? "pdf" : [
	"image/jpeg",
	"image/png",
	"image/webp",
	"image/gif"
].includes(e) ? "image" : e === "text/plain" ? "text" : "none" : "none", Pe = (e, t) => {
	if (e.device_id) return {
		kind: "device",
		id: e.device_id
	};
	if (e.entity) {
		let n = t?.entities?.[e.entity]?.device_id;
		return n ? {
			kind: "device",
			id: n
		} : null;
	}
	return e.area ? {
		kind: "area",
		id: e.area
	} : null;
}, Fe = (e, t) => {
	let n;
	return (...r) => {
		n !== void 0 && clearTimeout(n), n = setTimeout(() => e(...r), t);
	};
}, Ie = {
	en: {
		"panel.title": "Documents",
		"panel.tab_search": "Search",
		"panel.tab_devices": "Devices without manual",
		"panel.no_access": "You have no access to documents. Ask an administrator for access.",
		"panel.not_loaded": "Paperless Lookup is not loaded. Check the integration.",
		"panel.error": "Paperless cannot be reached right now.",
		"search.placeholder": "Search title and content",
		"search.all_stores": "All stores",
		"search.from": "From",
		"search.to": "To",
		"search.clear": "Clear filters",
		"search.results": "{count} documents",
		"search.no_results": "No documents found.",
		"search.more": "Show more",
		"document.open": "Open",
		"document.download": "Download",
		"document.close": "Close",
		"document.no_preview": "No preview available for this file type.",
		"document.no_pdf_viewer": "This app cannot show PDFs. Use Open or Download for the full document.",
		"devices.none": "Every device has a manual.",
		"devices.link": "Link document",
		"devices.ignore": "Ignore",
		"devices.zigbee2mqtt": "Zigbee2MQTT page",
		"devices.search_manual": "Search a document to link",
		"card.no_target": "Choose a device, entity or area in the card editor.",
		"card.no_documents": "No documents.",
		"card.unlink": "Remove link",
		"editor.device": "Device",
		"editor.entity": "Entity (uses its device)",
		"editor.area": "Area",
		"editor.title": "Title",
		"editor.show_thumbnails": "Show thumbnails"
	},
	nl: {
		"panel.title": "Documenten",
		"panel.tab_search": "Zoeken",
		"panel.tab_devices": "Toestellen zonder handleiding",
		"panel.no_access": "Je hebt geen toegang tot documenten. Vraag toegang aan een beheerder.",
		"panel.not_loaded": "Paperless Lookup is niet geladen. Controleer de integratie.",
		"panel.error": "Paperless is nu niet bereikbaar.",
		"search.placeholder": "Zoek in titel en inhoud",
		"search.all_stores": "Alle winkels",
		"search.from": "Van",
		"search.to": "Tot",
		"search.clear": "Filters wissen",
		"search.results": "{count} documenten",
		"search.no_results": "Geen documenten gevonden.",
		"search.more": "Meer tonen",
		"document.open": "Openen",
		"document.download": "Downloaden",
		"document.close": "Sluiten",
		"document.no_preview": "Geen voorbeeld beschikbaar voor dit bestandstype.",
		"document.no_pdf_viewer": "Deze app kan geen pdf tonen. Gebruik Openen of Downloaden voor het volledige document.",
		"devices.none": "Elk toestel heeft een handleiding.",
		"devices.link": "Document koppelen",
		"devices.ignore": "Negeren",
		"devices.zigbee2mqtt": "Zigbee2MQTT-pagina",
		"devices.search_manual": "Zoek een document om te koppelen",
		"card.no_target": "Kies een toestel, entiteit of ruimte in de kaarteditor.",
		"card.no_documents": "Geen documenten.",
		"card.unlink": "Koppeling verwijderen",
		"editor.device": "Toestel",
		"editor.entity": "Entiteit (gebruikt het toestel ervan)",
		"editor.area": "Ruimte",
		"editor.title": "Titel",
		"editor.show_thumbnails": "Miniaturen tonen"
	}
}, Le = (e) => {
	let t = (e ?? "en").toLowerCase().split(/[-_]/)[0];
	return t in Ie ? t : "en";
}, X = (e, t, n = {}) => {
	let r = Ie[Le(e)][t];
	for (let [e, t] of Object.entries(n)) r = r.replace(`{${e}}`, String(t));
	return r;
}, Z = o`
  :host {
    color: var(--primary-text-color);
    font-family: var(--ha-font-family-body, var(--paper-font-body1_-_font-family, sans-serif));
  }
  button {
    font: inherit;
    cursor: pointer;
  }
  .doc {
    display: flex;
    gap: 12px;
    align-items: flex-start;
    width: 100%;
    padding: 10px 12px;
    border: none;
    border-bottom: 1px solid var(--divider-color);
    background: none;
    color: inherit;
    text-align: start;
    box-sizing: border-box;
  }
  .doc:hover,
  .doc:focus-visible {
    background: var(--secondary-background-color);
    outline: none;
  }
  .thumb {
    flex: 0 0 48px;
    width: 48px;
    height: 64px;
    object-fit: cover;
    border-radius: 4px;
    background: var(--secondary-background-color);
    border: 1px solid var(--divider-color);
  }
  .doc-body {
    min-width: 0;
    flex: 1;
  }
  .doc-title {
    font-weight: 500;
    overflow-wrap: anywhere;
  }
  .doc-meta {
    color: var(--secondary-text-color);
    font-size: 0.9em;
    margin-top: 2px;
  }
  .highlights {
    color: var(--secondary-text-color);
    font-size: 0.85em;
    margin-top: 4px;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .highlights mark {
    background: none;
    color: var(--primary-text-color);
    font-weight: 600;
  }
  .message {
    padding: 16px;
    color: var(--secondary-text-color);
  }
  .error {
    color: var(--error-color, #db4437);
  }
  .action {
    border: 1px solid var(--divider-color);
    border-radius: 18px;
    padding: 6px 14px;
    background: var(--card-background-color);
    color: var(--primary-text-color);
  }
  .action.primary {
    background: var(--primary-color);
    border-color: var(--primary-color);
    color: var(--text-primary-color, #fff);
  }
  a.link {
    color: var(--primary-color);
  }
`, Q = (e, t, n, r, i = I) => {
	let a = [
		Me(e.created, t),
		e.correspondent_name,
		e.category_name
	].filter(Boolean).join(" · ");
	return P`
    <div class="row">
      <button class="doc" @click=${() => n(e)}>
        ${r === void 0 ? I : r ? P`<img class="thumb" src=${r} alt="" loading="lazy" />` : P`<span class="thumb"></span>`}
        <span class="doc-body">
          <div class="doc-title">${e.title}</div>
          <div class="doc-meta">${a}</div>
          ${e.highlights?.length ? P`<div class="highlights">
                ${e.highlights.map((e) => e.match ? P`<mark>${e.text}</mark>` : e.text)}
              </div>` : I}
        </span>
      </button>
      ${i}
    </div>
  `;
}, Re = () => navigator.pdfViewerEnabled !== !1, ze = class extends G {
	static {
		this.properties = {
			hass: { attribute: !1 },
			document: { attribute: !1 },
			_preview: { state: !0 },
			_download: { state: !0 },
			_thumb: { state: !0 },
			_failed: { state: !0 }
		};
	}
	constructor() {
		super(), this._onKey = (e) => {
			e.key === "Escape" && this._close();
		}, this._failed = !1;
	}
	connectedCallback() {
		super.connectedCallback(), window.addEventListener("keydown", this._onKey);
	}
	disconnectedCallback() {
		window.removeEventListener("keydown", this._onKey), super.disconnectedCallback();
	}
	async firstUpdated() {
		try {
			let e = this.document.id, [t, n, r] = await Promise.all([
				J(this.hass, [e], "preview"),
				J(this.hass, [e], "download"),
				Re() ? Promise.resolve({}) : J(this.hass, [e], "thumb")
			]);
			this._preview = t[e], this._download = n[e], this._thumb = r[e], this._failed = this._preview === void 0;
		} catch {
			this._failed = !0;
		}
	}
	_close() {
		this.dispatchEvent(new CustomEvent("closed", {
			bubbles: !0,
			composed: !0
		}));
	}
	_open() {
		this._preview && window.open(this.hass.hassUrl(this._preview), "_blank", "noopener");
	}
	_body() {
		let e = this.hass.language;
		if (this._failed) return P`<div class="message error">${X(e, "panel.error")}</div>`;
		if (!this._preview) return P`<div class="message">…</div>`;
		switch (Ne(this.document.mime_type)) {
			case "pdf": return Re() ? P`<iframe src=${this._preview} title=${this.document.title}></iframe>` : P`<div class="fallback">
            ${this._thumb ? P`<img class="page" src=${this._thumb} alt=${this.document.title} />` : I}
            <div class="message">${X(e, "document.no_pdf_viewer")}</div>
          </div>`;
			case "text": return P`<iframe src=${this._preview} title=${this.document.title}></iframe>`;
			case "image": return P`<img class="full" src=${this._preview} alt=${this.document.title} />`;
			default: return P`<div class="message">${X(e, "document.no_preview")}</div>`;
		}
	}
	render() {
		let e = this.hass.language;
		return P`
      <div class="backdrop" @click=${this._close}></div>
      <section role="dialog" aria-modal="true" aria-label=${this.document.title}>
        <header>
          <h2>${this.document.title}</h2>
          <button class="action" @click=${this._close}>${X(e, "document.close")}</button>
        </header>
        <div class="body">${this._body()}</div>
        <footer>
          <button class="action" ?disabled=${!this._preview} @click=${this._open}>
            ${X(e, "document.open")}
          </button>
          ${this._download ? P`<a class="action primary" href=${this._download} download
                >${X(e, "document.download")}</a
              >` : I}
        </footer>
      </section>
    `;
	}
	static {
		this.styles = [Z, o`
      :host {
        position: fixed;
        inset: 0;
        z-index: 10;
        display: flex;
        align-items: center;
        justify-content: center;
      }
      .backdrop {
        position: absolute;
        inset: 0;
        background: rgba(0, 0, 0, 0.5);
      }
      section {
        position: relative;
        display: flex;
        flex-direction: column;
        width: min(960px, 100vw);
        height: min(92vh, 100dvh);
        background: var(--card-background-color, #fff);
        border-radius: var(--ha-card-border-radius, 12px);
        overflow: hidden;
      }
      header,
      footer {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px 12px;
      }
      header h2 {
        flex: 1;
        margin: 0;
        font-size: 1.1em;
        overflow-wrap: anywhere;
      }
      footer {
        justify-content: flex-end;
        border-top: 1px solid var(--divider-color);
      }
      footer a {
        text-decoration: none;
      }
      .body {
        flex: 1;
        min-height: 0;
        display: flex;
        background: var(--secondary-background-color);
      }
      iframe {
        flex: 1;
        border: 0;
        background: #fff;
      }
      .fallback {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 8px;
        padding: 16px;
        text-align: center;
      }
      img.page {
        max-width: min(100%, 420px);
        max-height: 70%;
        object-fit: contain;
        background: #fff;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.3);
      }
      img.full {
        max-width: 100%;
        max-height: 100%;
        margin: auto;
        object-fit: contain;
      }
      @media (max-width: 600px) {
        section {
          width: 100vw;
          height: 100dvh;
          border-radius: 0;
        }
      }
    `];
	}
}, $ = "paperless-lookup-card", Be = class extends G {
	static {
		this.properties = {
			hass: { attribute: !1 },
			_config: { state: !0 },
			_devices: { state: !0 },
			_error: { state: !0 },
			_thumbs: { state: !0 },
			_open: { state: !0 }
		};
	}
	constructor() {
		super(), this._thumbs = {};
	}
	static getConfigElement() {
		return document.createElement("paperless-lookup-card-editor");
	}
	static getStubConfig() {
		return { type: `custom:${$}` };
	}
	setConfig(e) {
		if (!e || typeof e != "object") throw Error("Invalid configuration");
		this._config = {
			show_thumbnails: !0,
			...e
		}, this._loadedFor = void 0;
	}
	getCardSize() {
		let e = this._devices?.reduce((e, t) => e + t.documents.length, 0) ?? 1;
		return 1 + Math.min(e, 6);
	}
	_t(e) {
		return X(this.hass?.language, e);
	}
	updated() {
		if (!this.hass || !this._config) return;
		let e = Pe(this._config, this.hass), t = e ? `${e.kind}:${e.id}` : "none";
		t !== this._loadedFor && (this._loadedFor = t, this._load(e));
	}
	async _load(e) {
		if (!this.hass || !e) this._devices = void 0, this._error = e ? void 0 : "card.no_target";
		else try {
			if (this._devices = e.kind === "device" ? [await Se(this.hass, e.id)] : (await Ce(this.hass, e.id)).devices, this._error = void 0, this._config?.show_thumbnails) {
				let e = this._devices.flatMap((e) => e.documents.map((e) => e.id));
				this._thumbs = await J(this.hass, e, "thumb");
			}
		} catch (e) {
			this._devices = void 0, this._error = Oe(e) === "not_loaded" ? "panel.not_loaded" : "panel.error";
		}
	}
	async _unlink(e, t) {
		if (!this.hass) return;
		let n = await Ee(this.hass, e, t.id);
		this._devices = this._devices?.map((t) => t.device_id === e ? n : t);
	}
	_device(e, t) {
		let n = this.hass?.language ?? "en", r = this.hass?.user?.is_admin ?? !1;
		return P`
      ${t ? P`<div class="device">${e.name}</div>` : I}
      ${e.documents.map((t) => Q(t, n, (e) => this._open = e, this._config?.show_thumbnails ? this._thumbs[t.id] ?? "" : void 0, r ? P`<button
                class="unlink"
                title=${this._t("card.unlink")}
                aria-label=${this._t("card.unlink")}
                @click=${() => this._unlink(e.device_id, t)}
              >
                ✕
              </button>` : I))}
      ${e.zigbee2mqtt_url ? P`<div class="fallback">
            <a class="link" href=${e.zigbee2mqtt_url} target="_blank" rel="noreferrer"
              >${this._t("devices.zigbee2mqtt")}</a
            >
          </div>` : I}
    `;
	}
	render() {
		let e = this._config;
		if (!e) return P``;
		let t = this._devices ?? [], n = t.every((e) => !e.documents.length && !e.zigbee2mqtt_url);
		return P`
      <ha-card .header=${e.title ?? I}>
        ${this._error ? P`<div class="message ${this._error === "card.no_target" ? "" : "error"}">
              ${this._t(this._error)}
            </div>` : this._devices === void 0 ? P`<div class="message">…</div>` : n ? P`<div class="message">${this._t("card.no_documents")}</div>` : t.map((n) => this._device(n, t.length > 1 || !!e.area))}
      </ha-card>
      ${this._open && this.hass ? P`<paperless-lookup-preview
            .hass=${this.hass}
            .document=${this._open}
            @closed=${() => this._open = void 0}
          ></paperless-lookup-preview>` : I}
    `;
	}
	static {
		this.styles = [Z, o`
      .device {
        padding: 12px 12px 4px;
        font-weight: 500;
        color: var(--secondary-text-color);
      }
      .row {
        display: flex;
        align-items: center;
      }
      .unlink {
        border: none;
        background: none;
        color: var(--secondary-text-color);
        padding: 12px;
      }
      .fallback {
        padding: 10px 12px;
      }
    `];
	}
}, Ve = class extends G {
	constructor(...e) {
		super(...e), this._schema = [
			{
				name: "device_id",
				selector: { device: {} }
			},
			{
				name: "entity",
				selector: { entity: {} }
			},
			{
				name: "area",
				selector: { area: {} }
			},
			{
				name: "title",
				selector: { text: {} }
			},
			{
				name: "show_thumbnails",
				selector: { boolean: {} }
			}
		], this._label = (e) => X(this.hass?.language, `editor.${e.name === "device_id" ? "device" : e.name}`);
	}
	static {
		this.properties = {
			hass: { attribute: !1 },
			_config: { state: !0 }
		};
	}
	setConfig(e) {
		this._config = e;
	}
	_changed(e) {
		let t = {
			...e.detail.value,
			type: `custom:${$}`
		};
		for (let e of [
			"device_id",
			"entity",
			"area",
			"title"
		]) t[e] || delete t[e];
		this.dispatchEvent(new CustomEvent("config-changed", {
			detail: { config: t },
			bubbles: !0,
			composed: !0
		}));
	}
	render() {
		return !this.hass || !this._config ? P`` : P`<ha-form
      .hass=${this.hass}
      .data=${{
			show_thumbnails: !0,
			...this._config
		}}
      .schema=${this._schema}
      .computeLabel=${this._label}
      @value-changed=${this._changed}
    ></ha-form>`;
	}
};
window.customCards = window.customCards ?? [], window.customCards.some((e) => e.type === "paperless-lookup-card") || window.customCards.push({
	type: $,
	name: "Paperless Lookup",
	description: "Documents (manuals, receipts, …) of a device or an area."
});
// src/panel.ts
var He = class extends G {
	static {
		this.properties = {
			hass: { attribute: !1 },
			narrow: { type: Boolean },
			_status: { state: !0 },
			_access: { state: !0 },
			_filters: { state: !0 },
			_state: { state: !0 },
			_results: { state: !0 },
			_count: { state: !0 },
			_searching: { state: !0 },
			_searchError: { state: !0 },
			_thumbs: { state: !0 },
			_open: { state: !0 },
			_tab: { state: !0 },
			_devices: { state: !0 },
			_linking: { state: !0 },
			_linkQuery: { state: !0 },
			_linkResults: { state: !0 }
		};
	}
	constructor() {
		super(), this._searchSeq = 0, this._initialized = !1, this._debouncedSearch = Fe(() => void this._search(), 300), this._debouncedLinkSearch = Fe((e) => void this._searchLink(e), 300), this.narrow = !1, this._status = "loading", this._state = ke(), this._results = [], this._count = 0, this._searching = !1, this._searchError = !1, this._thumbs = {}, this._tab = "search", this._linkQuery = "", this._linkResults = [];
	}
	_t(e, t) {
		return X(this.hass?.language, e, t);
	}
	updated() {
		this.hass && !this._initialized && (this._initialized = !0, this._load());
	}
	async _load() {
		try {
			if (this._access = await be(this.hass), !this._access.allowed) {
				this._status = "no_access";
				return;
			}
			this._filters = await xe(this.hass), this._status = "ready", await this._search();
		} catch (e) {
			this._status = Oe(e) === "not_loaded" ? "not_loaded" : "error";
		}
	}
	async _search(e = !1) {
		let t = ++this._searchSeq;
		this._searching = !0, this._searchError = !1;
		try {
			let n = await q(this.hass, Ae(this._state));
			if (t !== this._searchSeq) return;
			this._results = e ? [...this._results, ...n.results] : n.results, this._count = n.count;
			let r = n.results.map((e) => e.id).filter((e) => !(e in this._thumbs)), i = await J(this.hass, r, "thumb");
			t === this._searchSeq && (this._thumbs = {
				...this._thumbs,
				...i
			});
		} catch {
			t === this._searchSeq && (this._searchError = !0);
		} finally {
			t === this._searchSeq && (this._searching = !1);
		}
	}
	_update(e, t = !1) {
		this._state = {
			...this._state,
			...e,
			page: e.page ?? 1
		}, t ? this._debouncedSearch() : this._search(e.page !== void 0 && e.page > 1);
	}
	async _loadDevices() {
		try {
			this._devices = (await we(this.hass)).devices;
		} catch {
			this._devices = [];
		}
	}
	_selectTab(e) {
		this._tab = e, e === "devices" && this._devices === void 0 && this._loadDevices();
	}
	async _searchLink(e) {
		this._linkQuery = e;
		let t = this._access?.device_categories.map((e) => e.id) ?? [];
		if (!t.length) {
			this._linkResults = [];
			return;
		}
		let n = await q(this.hass, {
			query: e,
			categories: t,
			page: 1,
			page_size: 10
		});
		this._linkResults = n.results;
	}
	async _link(e, t) {
		await Te(this.hass, e, t), this._linking = void 0, await this._loadDevices();
	}
	async _ignore(e) {
		await De(this.hass, e, !0), await this._loadDevices();
	}
	render() {
		return P`
      <header class="toolbar">
        <ha-menu-button .hass=${this.hass} .narrow=${this.narrow}></ha-menu-button>
        <h1>${this._t("panel.title")}</h1>
      </header>
      ${this._status === "ready" && this._access?.is_admin ? P`<nav class="tabs" role="tablist">
            ${["search", "devices"].map((e) => P`<button
                role="tab"
                aria-selected=${this._tab === e}
                class=${this._tab === e ? "tab active" : "tab"}
                @click=${() => this._selectTab(e)}
              >
                ${this._t(e === "search" ? "panel.tab_search" : "panel.tab_devices")}
              </button>`)}
          </nav>` : I}
      <main>${this._content()}</main>
      ${this._open ? P`<paperless-lookup-preview
            .hass=${this.hass}
            .document=${this._open}
            @closed=${() => this._open = void 0}
          ></paperless-lookup-preview>` : I}
    `;
	}
	_content() {
		switch (this._status) {
			case "loading": return P`<div class="message">…</div>`;
			case "no_access": return P`<div class="message">${this._t("panel.no_access")}</div>`;
			case "not_loaded": return P`<div class="message">${this._t("panel.not_loaded")}</div>`;
			case "error": return P`<div class="message error">${this._t("panel.error")}</div>`;
			default: return this._tab === "devices" ? this._devicesTab() : this._searchTab();
		}
	}
	_searchTab() {
		let e = this._filters, t = this.hass.language, n = this._state;
		return P`
      <div class="search">
        <input
          type="search"
          enterkeyhint="search"
          .value=${n.query}
          placeholder=${this._t("search.placeholder")}
          aria-label=${this._t("search.placeholder")}
          @input=${(e) => this._update({ query: e.target.value }, !0)}
        />
        <div class="chips" role="group">
          ${e?.categories.map((e) => P`<button
              class=${n.categories.includes(e.id) ? "chip selected" : "chip"}
              aria-pressed=${n.categories.includes(e.id)}
              @click=${() => this._update({ categories: je(n.categories, e.id) })}
            >
              ${e.name}
            </button>`)}
        </div>
        <div class="filters">
          <select
            aria-label=${this._t("search.all_stores")}
            @change=${(e) => {
			let t = e.target.value;
			this._update({ correspondent: t ? Number(t) : null });
		}}
          >
            <option value="" ?selected=${n.correspondent === null}>
              ${this._t("search.all_stores")}
            </option>
            ${e?.correspondents.map((e) => P`<option value=${e.id} ?selected=${n.correspondent === e.id}>
                  ${e.name}
                </option>`)}
          </select>
          <label
            >${this._t("search.from")}
            <input
              type="date"
              .value=${n.dateFrom}
              min=${e?.date_min ?? I}
              max=${e?.date_max ?? I}
              @change=${(e) => this._update({ dateFrom: e.target.value })}
          /></label>
          <label
            >${this._t("search.to")}
            <input
              type="date"
              .value=${n.dateTo}
              min=${e?.date_min ?? I}
              max=${e?.date_max ?? I}
              @change=${(e) => this._update({ dateTo: e.target.value })}
          /></label>
          <button class="action" @click=${() => this._update(ke())}>
            ${this._t("search.clear")}
          </button>
        </div>
      </div>
      <div class="results" aria-live="polite" aria-busy=${this._searching}>
        ${this._searchError ? P`<div class="message error">${this._t("panel.error")}</div>` : !this._results.length && !this._searching ? P`<div class="message">${this._t("search.no_results")}</div>` : P`<div class="count">${this._t("search.results", { count: this._count })}</div>
                ${this._results.map((e) => Q(e, t, (e) => this._open = e, this._thumbs[e.id] ?? ""))}
                ${this._count > n.page * 25 ? P`<button
                      class="action more"
                      ?disabled=${this._searching}
                      @click=${() => this._update({ page: n.page + 1 })}
                    >
                      ${this._t("search.more")}
                    </button>` : I}`}
      </div>
    `;
	}
	_devicesTab() {
		if (this._devices === void 0) return P`<div class="message">…</div>`;
		if (!this._devices.length) return P`<div class="message">${this._t("devices.none")}</div>`;
		let e = this.hass.language;
		return P`<ul class="devices">
      ${this._devices.map((t) => P`<li>
          <div class="device-head">
            <div class="doc-body">
              <div class="doc-title">${t.name}</div>
              <div class="doc-meta">
                ${[
			t.manufacturer,
			t.model,
			t.model_id
		].filter(Boolean).join(" · ")}
              </div>
            </div>
            ${t.zigbee2mqtt_url ? P`<a class="link" href=${t.zigbee2mqtt_url} target="_blank" rel="noreferrer"
                  >${this._t("devices.zigbee2mqtt")}</a
                >` : I}
          </div>
          <div class="device-actions">
            <button
              class="action primary"
              @click=${() => {
			this._linking = this._linking === t.device_id ? void 0 : t.device_id, this._linking && this._searchLink(t.model_id ?? t.model ?? "");
		}}
            >
              ${this._t("devices.link")}
            </button>
            <button class="action" @click=${() => this._ignore(t.device_id)}>
              ${this._t("devices.ignore")}
            </button>
          </div>
          ${this._linking === t.device_id ? P`<div class="link-search">
                <input
                  type="search"
                  .value=${this._linkQuery}
                  placeholder=${this._t("devices.search_manual")}
                  aria-label=${this._t("devices.search_manual")}
                  @input=${(e) => this._debouncedLinkSearch(e.target.value)}
                />
                ${this._linkResults.map((n) => Q(n, e, () => this._link(t.device_id, n.id)))}
              </div>` : I}
        </li>`)}
    </ul>`;
	}
	static {
		this.styles = [Z, o`
      :host {
        display: block;
        min-height: 100vh;
        background: var(--primary-background-color);
      }
      .toolbar {
        display: flex;
        align-items: center;
        gap: 4px;
        height: var(--header-height, 56px);
        padding: 0 12px;
        background: var(--app-header-background-color, var(--primary-color));
        color: var(--app-header-text-color, var(--text-primary-color, #fff));
        position: sticky;
        top: 0;
        z-index: 2;
      }
      h1 {
        margin: 0;
        font-size: 20px;
        font-weight: 400;
      }
      .tabs {
        display: flex;
        background: var(--card-background-color);
        border-bottom: 1px solid var(--divider-color);
      }
      .tab {
        flex: 1;
        padding: 12px;
        border: none;
        border-bottom: 2px solid transparent;
        background: none;
        color: var(--secondary-text-color);
      }
      .tab.active {
        color: var(--primary-color);
        border-bottom-color: var(--primary-color);
      }
      main {
        max-width: 900px;
        margin: 0 auto;
      }
      .search {
        padding: 12px;
        display: flex;
        flex-direction: column;
        gap: 10px;
      }
      input,
      select {
        font: inherit;
        color: var(--primary-text-color);
        background: var(--card-background-color);
        border: 1px solid var(--divider-color);
        border-radius: 8px;
        padding: 10px 12px;
        box-sizing: border-box;
      }
      input[type="search"] {
        width: 100%;
        font-size: 16px; /* no zoom on iOS */
      }
      .chips {
        display: flex;
        gap: 8px;
        overflow-x: auto;
        padding-bottom: 2px;
      }
      .chip {
        flex: none;
        border: 1px solid var(--divider-color);
        border-radius: 16px;
        padding: 6px 12px;
        background: var(--card-background-color);
        color: var(--primary-text-color);
      }
      .chip.selected {
        background: var(--primary-color);
        border-color: var(--primary-color);
        color: var(--text-primary-color, #fff);
      }
      .filters {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        align-items: center;
      }
      .filters label {
        display: flex;
        align-items: center;
        gap: 6px;
        color: var(--secondary-text-color);
      }
      .results,
      .devices {
        background: var(--card-background-color);
        border-radius: var(--ha-card-border-radius, 12px);
        margin: 0 12px 24px;
        overflow: hidden;
      }
      .row {
        display: flex;
        align-items: center;
      }
      .count {
        padding: 10px 12px;
        color: var(--secondary-text-color);
        border-bottom: 1px solid var(--divider-color);
      }
      .more {
        display: block;
        margin: 12px auto;
      }
      .devices {
        list-style: none;
        padding: 0;
      }
      .devices li {
        padding: 12px;
        border-bottom: 1px solid var(--divider-color);
      }
      .device-head {
        display: flex;
        gap: 12px;
        align-items: center;
      }
      .device-actions {
        display: flex;
        gap: 8px;
        margin-top: 8px;
      }
      .link-search {
        margin-top: 8px;
      }
      .link-search input {
        width: 100%;
      }
    `];
	}
}, Ue = [
	["paperless-lookup-preview", ze],
	["paperless-lookup-panel", He],
	[$, Be],
	["paperless-lookup-card-editor", Ve]
], We = () => {
	for (let [e, t] of Ue) customElements.get(e) || customElements.define(e, t);
}, Ge = (e = document, t = 50, n = We) => {
	if (!e.querySelector("home-assistant") || window.customElements.get("home-assistant")) {
		n();
		return;
	}
	let r = () => {
		window.customElements.get("home-assistant") ? n() : setTimeout(r, t);
	};
	setTimeout(r, t);
};
Ge();
export { Ue as ELEMENTS, We as registerElements, Ge as registerWhenReady };
