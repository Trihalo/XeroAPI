import React, { useState } from "react";

import Sidebar from "../components/Sidebar";
import RequestButton from "../components/RequestButton";

export default function History() {
  return (
    <div className="flex w-screen h-screen">
      {/* Sidebar */}
      <Sidebar />

      {/* Main Content */}
      <div className="flex-1 p-6 bg-base-200 pt-10">
        <p className="text-6xl text-primary-content">Trihalo Accountancy</p>
        <p className="text-primary pt-8">Let's make this day efficient!</p>

        {/* Card Container */}
        <div className="mt-6 mr-10 bg-base-100 text-primary-content shadow-lg rounded-box">
          <div className="card-body">Hi</div>
        </div>
      </div>
    </div>
  );
}
