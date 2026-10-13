import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { homeFor, isStaff, useAuth } from "../lib/auth";
import { Emblem, Icon } from "./icons";
import { initials } from "./ui";

/** Pages that draw their own full-width banner. */
const FULL_BLEED = ["/", "/login", "/recruit", "/activate"];

export default function Layout() {
  const { me, signOut } = useAuth();
  const nav = useNavigate();
  const { pathname } = useLocation();
  return (
    <div className="shell">
      <a href="#main" className="skip">Skip to content</a>
      <div className="utility">
        <div className="utility-inner">
          <a href="https://www.nfsu.ac.in/" target="_blank" rel="noopener noreferrer"><Icon name="globe" />NFSU website</a>
          <a href="mailto:placement-cell@nfsu.local"><Icon name="mail" />placement-cell@nfsu.local</a>
          <span className="spacer" />
          <span className="session-pill">Placement session 2026–27</span>
        </div>
      </div>
      <header className="topbar">
        <div className="topbar-inner">
          <NavLink to="/" className="brand" aria-label="NFSU Training and Placement Cell home">
            <Emblem />
            <span className="brand-text">
              <small>Training and Placement Cell</small>
              <strong>National Forensic Sciences University</strong>
            </span>
          </NavLink>
          <nav className="nav" aria-label="Main">
            <NavLink to="/" end><Icon name="home" />Overview</NavLink>
            {me && <NavLink to="/bulletin"><Icon name="megaphone" />Bulletin</NavLink>}
            {me?.role === "student" && <NavLink to="/student"><Icon name="grid" />My placement</NavLink>}
            {me?.role === "recruiter" && <NavLink to="/recruiter"><Icon name="users" />Candidates</NavLink>}
            {isStaff(me?.role) && <NavLink to="/staff"><Icon name="grid" />Console</NavLink>}
            {!me && <NavLink to="/recruit"><Icon name="handshake" />Recruit at NFSU</NavLink>}
          </nav>
          <div className="who">
            {me ? (
              <>
                <span className="avatar" aria-hidden="true">{initials(me.name)}</span>
                <span className="who-name">
                  {me.name}
                  <small>{me.company ?? me.role}</small>
                </span>
                <button className="btn-quiet btn-sm" onClick={async () => { await signOut(); nav("/"); }}><Icon name="logout" />Sign out</button>
              </>
            ) : (
              <NavLink className="btn" to="/login"><Icon name="login" />Sign in</NavLink>
            )}
          </div>
        </div>
      </header>
      <main id="main" className={`main${FULL_BLEED.includes(pathname) ? " full" : ""}`}>
        <Outlet />
      </main>
      <footer className="foot">
        <div className="foot-inner">
          <div>
            <div className="brand">
              <Emblem />
              <span className="brand-text"><small>Training and Placement Cell</small><strong>NFSU, Gandhinagar</strong></span>
            </div>
            <p>The Placement Cell connects students of the five computing programmes with verified recruiters. Every decision is checked against the placement policy and recorded in a tamper-evident audit log.</p>
          </div>
          <div>
            <h4>Quick links</h4>
            <ul>
              <li><NavLink to="/">Placement overview</NavLink></li>
              <li><NavLink to="/recruit">Recruit at NFSU</NavLink></li>
              <li>{me ? <NavLink to={homeFor(me.role)}>My dashboard</NavLink> : <NavLink to="/login">Sign in</NavLink>}</li>
              <li><a href="/#faq">Frequently asked questions</a></li>
            </ul>
          </div>
          <div>
            <h4>Programmes</h4>
            <ul>
              <li>M.Tech. Computer Science</li>
              <li>M.Tech. AI and Data Science</li>
              <li>B.Tech.–M.Tech. CSE</li>
              <li>M.Sc. Computer Science</li>
              <li>M.Sc. Digital Forensics and IS</li>
            </ul>
          </div>
          <div>
            <h4>Contact</h4>
            <ul>
              <li><Icon name="pin" />Placement Cell, NFSU, Sector 9, Gandhinagar, Gujarat 382007</li>
              <li><Icon name="mail" /><a href="mailto:placement-cell@nfsu.local">placement-cell@nfsu.local</a></li>
              <li><Icon name="clock" />Monday to Friday, 10:00 to 17:30</li>
            </ul>
          </div>
        </div>
        <div className="foot-base">
          <div>
            <span>© 2026 National Forensic Sciences University · Training and Placement Cell</span>
            <span>
              Campus photos: Rushi Mehta, <a href="https://creativecommons.org/licenses/by/3.0/" target="_blank" rel="noopener noreferrer">CC BY 3.0</a>, via{" "}
              <a href="https://commons.wikimedia.org/wiki/Category:National_Forensic_Sciences_University" target="_blank" rel="noopener noreferrer">Wikimedia Commons</a> (cropped)
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
}
